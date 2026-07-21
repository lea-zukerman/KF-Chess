"""Single-process WebSocket server: one game, driven entirely through
GameSession/GameEngine, never touching Board internals directly."""

import argparse
import asyncio
import logging
import time

import websockets

from kungfu_chess.model.board import Board
from kungfu_chess.model.game_state import GameState
from kungfu_chess.bus.event_bus import EventBus
from kungfu_chess.app.game_session import GameSession
from kungfu_chess.rules.algebraic import algebraic_to_cell

logger = logging.getLogger(__name__)

DEFAULT_BOARD_TEXT = """bR bN bB bQ bK bB bN bR
bP bP bP bP bP bP bP bP
.  .  .  .  .  .  .  .
.  .  .  .  .  .  .  .
.  .  .  .  .  .  .  .
.  .  .  .  .  .  .  .
wP wP wP wP wP wP wP wP
wR wN wB wQ wK wB wN wR"""

TICK_INTERVAL_S = 0.1


class GameServer:
    """Holds one GameSession and the WebSocket connections attached to it."""

    def __init__(self, board_text: str = DEFAULT_BOARD_TEXT):
        board = Board.from_text_lines(board_text.strip().split("\n"))
        self.bus = EventBus()
        self.session = GameSession(board, self.bus)
        self.game_state = GameState()
        self.clients: dict = {}  # websocket -> role ('w' / 'b' / 'observer')
        self._start_time = time.monotonic()

        # Bus handlers are synchronous; bridge them to the async broadcast
        # via a queue so score/move-log/game-over updates are what actually
        # drives broadcasts, instead of an unconditional per-tick broadcast.
        self._broadcast_queue: asyncio.Queue = asyncio.Queue()
        for event_type in ("move_logged", "score_changed", "game_over"):
            self.bus.subscribe(event_type, self._make_bus_handler(event_type))

    def _make_bus_handler(self, event_type: str):
        def handler(payload: dict) -> None:
            self._broadcast_queue.put_nowait((event_type, payload))
        return handler

    def _now_ms(self) -> int:
        return int((time.monotonic() - self._start_time) * 1000)

    def _assign_role(self) -> str:
        colors_taken = {role for role in self.clients.values() if role in ("w", "b")}
        if "w" not in colors_taken:
            return "w"
        if "b" not in colors_taken:
            return "b"
        return "observer"

    async def handle_client(self, websocket) -> None:
        role = self._assign_role()
        if role != "observer":
            await self._notify_others(f"player_joined: {role}")
        self.clients[websocket] = role
        logger.info("client connected as %s (total=%d)", role, len(self.clients))
        await websocket.send(f"role: {role}")
        await self._broadcast_state()
        try:
            async for message in websocket:
                logger.info("received from %s: %r", role, message)
                await self._handle_command(websocket, role, message)
        finally:
            del self.clients[websocket]
            logger.info("client (%s) disconnected (total=%d)", role, len(self.clients))

    async def _handle_command(self, websocket, role: str, message: str) -> None:
        parts = message.strip().split()
        if not parts:
            return

        if role == "observer":
            await websocket.send("error: observers cannot move")
            return

        if role != self.game_state.current_turn:
            await websocket.send("error: not your turn")
            return

        now_ms = self._now_ms()
        try:
            if parts[0] == "move" and len(parts) == 3:
                from_row, from_col = algebraic_to_cell(parts[1], self.session.engine.board.rows)
                to_row, to_col = algebraic_to_cell(parts[2], self.session.engine.board.rows)
                accepted = self.session.request_move(
                    from_row, from_col, to_row, to_col, now_ms, self.game_state.current_turn
                )
            elif parts[0] == "jump" and len(parts) == 2:
                row, col = algebraic_to_cell(parts[1], self.session.engine.board.rows)
                accepted = self.session.request_jump(row, col, now_ms, self.game_state.current_turn)
            else:
                await websocket.send(f"error: unknown command {message!r}")
                return
        except ValueError as exc:
            await websocket.send(f"error: {exc}")
            return

        if not accepted:
            await websocket.send("error: illegal move")
            return

        self.game_state.switch_turn()
        await self._broadcast_state()

    async def _broadcast_state(self) -> None:
        text = self._format_snapshot(self.session.snapshot(self._now_ms()))
        logger.info("broadcasting state to %d client(s)", len(self.clients))
        for ws in list(self.clients):
            await ws.send(text)

    async def _notify_others(self, text: str) -> None:
        logger.info("notifying %d existing client(s): %s", len(self.clients), text)
        for ws in list(self.clients):
            await ws.send(text)

    def _format_snapshot(self, snapshot: dict) -> str:
        lines = [
            "board:",
            snapshot["board"],
            f"score: w:{snapshot['score']['w']} b:{snapshot['score']['b']}",
            f"turn: {self.game_state.current_turn}",
            f"game_over: {'true' if snapshot['game_over'] else 'false'}",
        ]
        return "\n".join(lines)

    async def tick_loop(self) -> None:
        while True:
            await asyncio.sleep(TICK_INTERVAL_S)
            self.session.tick(self._now_ms())

    async def dispatch_broadcasts(self) -> None:
        """Broadcasts driven by the bus: fires when GameSession actually
        publishes move_logged/score_changed/game_over, not on a blind timer."""
        while True:
            event_type, _payload = await self._broadcast_queue.get()
            logger.info("bus event %s -> broadcasting state", event_type)
            await self._broadcast_state()


async def run_server(host: str = "localhost", port: int = 8765) -> None:
    server = GameServer()
    asyncio.create_task(server.tick_loop())
    asyncio.create_task(server.dispatch_broadcasts())
    async with websockets.serve(server.handle_client, host, port):
        logger.info("server listening on %s:%d", host, port)
        await asyncio.Future()  # run forever


def main() -> None:
    parser = argparse.ArgumentParser(description="Kung Fu Chess WebSocket server")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(run_server(args.host, args.port))


if __name__ == "__main__":
    main()
