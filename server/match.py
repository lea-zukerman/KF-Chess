"""Match: one in-progress game between two matched players.

Extracted from what used to be GameServer's per-process state, so that
multiple games can run concurrently once matchmaking hands out pairs.
GameServer (the lobby) creates one Match per pair and hands each player's
websocket off to it; Match owns the bus, GameSession, connection tracking,
tick loop, broadcast dispatch, ELO update, and disconnect/auto-resign
handling for that one game.
"""

import asyncio
import logging
import time

import websockets

from kungfu_chess.model.board import Board
from kungfu_chess.model.game_state import GameState
from kungfu_chess.bus.event_bus import EventBus
from kungfu_chess.app.game_session import GameSession
from kungfu_chess.rules.algebraic import algebraic_to_cell

from . import db, elo

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
DISCONNECT_RESIGN_SECONDS = 20


class Match:
    """Holds one GameSession and the connections attached to it.

    white_username/black_username are already decided by the caller
    (matchmaking) before a Match is created -- unlike the old single-game
    GameServer, Match never assigns roles itself.
    """

    def __init__(self, white_username: str, black_username: str, db_conn, board_text: str = DEFAULT_BOARD_TEXT):
        board = Board.from_text_lines(board_text.strip().split("\n"))
        self.bus = EventBus()
        self.session = GameSession(board, self.bus)
        self.game_state = GameState()
        self.game_state.white_name = white_username
        self.game_state.black_name = black_username
        self.db_conn = db_conn
        self.clients: dict = {}  # websocket -> role ('w' / 'b' / 'observer')
        self._start_time = time.monotonic()
        self._tick_task = None
        self._dispatch_task = None

        self._broadcast_queue: asyncio.Queue = asyncio.Queue()
        for event_type in ("move_logged", "score_changed", "game_over"):
            self.bus.subscribe(event_type, self._make_bus_handler(event_type))

    def _make_bus_handler(self, event_type: str):
        def handler(payload: dict) -> None:
            self._broadcast_queue.put_nowait((event_type, payload))
        return handler

    def _now_ms(self) -> int:
        return int((time.monotonic() - self._start_time) * 1000)

    def start(self) -> None:
        self._tick_task = asyncio.create_task(self.tick_loop())
        self._dispatch_task = asyncio.create_task(self.dispatch_broadcasts())

    def stop(self) -> None:
        if self._tick_task is not None:
            self._tick_task.cancel()
        if self._dispatch_task is not None:
            self._dispatch_task.cancel()

    async def join(self, websocket, role: str) -> None:
        """Attach an already-authenticated connection to this match.

        role is 'w', 'b', or 'observer', decided by the caller before this
        is called (matchmaking assigns 'w'/'b'; anyone else is 'observer').
        """
        username = self.game_state.white_name if role == "w" else \
            self.game_state.black_name if role == "b" else None

        if role != "observer":
            await self._notify_others(f"player_joined: {role} ({username})")
        self.clients[websocket] = role
        logger.info("client '%s' joined match as %s (total=%d)", username, role, len(self.clients))
        await websocket.send(f"role: {role}")
        await self._broadcast_state()

        try:
            async for message in websocket:
                logger.info("received from %s '%s': %r", role, username, message)
                await self._handle_command(websocket, role, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            del self.clients[websocket]
            logger.info("client '%s' (%s) left match (total=%d)", username, role, len(self.clients))
            if role in ("w", "b"):
                await self._handle_disconnect(role)

    async def _handle_disconnect(self, role: str) -> None:
        if self.session.engine.is_game_over():
            return

        winner = "b" if role == "w" else "w"
        for remaining in range(DISCONNECT_RESIGN_SECONDS, 0, -1):
            await self._notify_others(f"resign_countdown: {remaining}")
            await asyncio.sleep(1)

        if self.session.engine.is_game_over():
            return

        logger.info("auto-resigning %s after disconnect timeout", role)
        self.session.engine.resign(winner)
        # Don't apply the ELO update / broadcast here: the running tick_loop
        # will notice is_game_over() flipped on its next tick and drive both
        # through the same bus path king-capture already uses (see
        # dispatch_broadcasts) -- doing it here too would double-apply it.

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
        white_elo = db.get_elo(self.db_conn, self.game_state.white_name)
        black_elo = db.get_elo(self.db_conn, self.game_state.black_name)
        lines = [
            "board:",
            snapshot["board"],
            f"players: w:{self.game_state.white_name} b:{self.game_state.black_name}",
            f"elo: w:{white_elo} b:{black_elo}",
            f"score: w:{snapshot['score']['w']} b:{snapshot['score']['b']}",
            f"turn: {self.game_state.current_turn}",
            f"game_over: {'true' if snapshot['game_over'] else 'false'}",
        ]
        return "\n".join(lines)

    def _apply_elo_update(self) -> None:
        winner = self.session.engine.winner()
        if winner is None:
            return
        white_elo = db.get_elo(self.db_conn, self.game_state.white_name)
        black_elo = db.get_elo(self.db_conn, self.game_state.black_name)
        new_white, new_black = elo.compute_new_ratings(white_elo, black_elo, winner)
        db.update_elo(self.db_conn, self.game_state.white_name, new_white)
        db.update_elo(self.db_conn, self.game_state.black_name, new_black)
        logger.info(
            "elo updated: w:%d->%d b:%d->%d", white_elo, new_white, black_elo, new_black
        )

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
            if event_type == "game_over":
                self._apply_elo_update()
            await self._broadcast_state()
