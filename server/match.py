"""Match: one in-progress game between two matched players.

Owns the bus, GameSession, connection tracking, tick loop, broadcast
dispatch, ELO update, and disconnect/auto-resign handling for one game.
Talks to the network only through server.connection.Connection (protocol
message objects in/out) and to game rules only through kungfu_chess -- it
never touches a raw websocket, JSON, or chess rule logic directly.
"""

import asyncio
import logging
import time

from kungfu_chess.model.board import Board
from kungfu_chess.model.game_state import GameState
from kungfu_chess.bus.event_bus import EventBus
from kungfu_chess.app.game_session import GameSession

from protocol.messages import MoveRejected, PlayerJoined, ResignCountdown, RoleAssigned, StateUpdate

from . import commands, db, elo
from .connection import Connection, ConnectionClosed

logger = logging.getLogger(__name__)

DEFAULT_BOARD_TEXT = """bR bN bB bQ bK bB bN bR
bP bP bP bP bP bP bP bP
.  .  .  .  .  .  .  .
.  .  .  .  .  .  .  .
.  .  .  .  .  .  .  .
.  .  .  .  .  .  .  .
wP wP wP wP wP wP wP wP
wR wN wB wQ wK wB wN wR"""

MOVE_ERROR_OBSERVER = "OBSERVER_CANNOT_MOVE"
MOVE_ERROR_WRONG_TURN = "NOT_YOUR_TURN"

TICK_INTERVAL_S = 0.1
DISCONNECT_RESIGN_SECONDS = 20


class Match:
    """Holds one GameSession and the connections attached to it.

    white_username/black_username are already decided by the caller
    (matchmaking) before a Match is created -- Match never assigns roles
    itself.
    """

    def __init__(self, white_username: str, black_username: str, db_conn, board_text: str = DEFAULT_BOARD_TEXT):
        board = Board.from_text_lines(board_text.strip().split("\n"))
        self.bus = EventBus()
        self.session = GameSession(board, self.bus)
        self.game_state = GameState()
        self.game_state.white_name = white_username
        self.game_state.black_name = black_username
        self.db_conn = db_conn
        self.clients: dict[Connection, str] = {}  # Connection -> role ('w' / 'b' / 'observer')
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

    def now_ms(self) -> int:
        return int((time.monotonic() - self._start_time) * 1000)

    def start(self) -> None:
        self._tick_task = asyncio.create_task(self.tick_loop())
        self._dispatch_task = asyncio.create_task(self.dispatch_broadcasts())

    def stop(self) -> None:
        if self._tick_task is not None:
            self._tick_task.cancel()
        if self._dispatch_task is not None:
            self._dispatch_task.cancel()

    async def join(self, connection: Connection, role: str) -> None:
        """Attach an already-authenticated connection to this match.

        role is 'w', 'b', or 'observer', decided by the caller before this
        is called (matchmaking assigns 'w'/'b'; anyone else is 'observer').
        """
        username = self.game_state.white_name if role == "w" else \
            self.game_state.black_name if role == "b" else None

        if role != "observer":
            await self._notify_others(PlayerJoined(role, username))
        self.clients[connection] = role
        logger.info("client '%s' joined match as %s (total=%d)", username, role, len(self.clients))
        await connection.send(RoleAssigned(role))
        await self._broadcast_state()

        try:
            async for message in connection:
                logger.info("received from %s '%s': %r", role, username, message)
                await self._handle_message(connection, role, message)
        except ConnectionClosed:
            pass
        finally:
            del self.clients[connection]
            logger.info("client '%s' (%s) left match (total=%d)", username, role, len(self.clients))
            if role in ("w", "b"):
                await self._handle_disconnect(role)

    async def _handle_disconnect(self, role: str) -> None:
        if self.session.engine.is_game_over():
            return

        winner = "b" if role == "w" else "w"
        for remaining in range(DISCONNECT_RESIGN_SECONDS, 0, -1):
            await self._notify_others(ResignCountdown(remaining))
            await asyncio.sleep(1)

        if self.session.engine.is_game_over():
            return

        logger.info("auto-resigning %s after disconnect timeout", role)
        self.session.engine.resign(winner)
        # Don't apply the ELO update / broadcast here: the running tick_loop
        # will notice is_game_over() flipped on its next tick and drive both
        # through the same bus path king-capture already uses (see
        # dispatch_broadcasts) -- doing it here too would double-apply it.

    async def _handle_message(self, connection: Connection, role: str, message: object) -> None:
        error = self._authorize(role) or commands.dispatch(self, role, message, self.now_ms())
        if error is not None:
            await connection.send(error)
            return

        self.game_state.switch_turn()
        await self._broadcast_state()

    def _authorize(self, role: str) -> MoveRejected | None:
        checks = [
            (role == "observer", MOVE_ERROR_OBSERVER),
            (role != self.game_state.current_turn, MOVE_ERROR_WRONG_TURN),
        ]
        for is_blocked, reason in checks:
            if is_blocked:
                return MoveRejected(reason)
        return None

    async def _broadcast_state(self) -> None:
        message = self._state_update()
        logger.info("broadcasting state to %d client(s)", len(self.clients))
        for connection in list(self.clients):
            await connection.send(message)

    async def _notify_others(self, message: object) -> None:
        logger.info("notifying %d existing client(s): %s", len(self.clients), message)
        for connection in list(self.clients):
            await connection.send(message)

    def _state_update(self) -> StateUpdate:
        snapshot = self.session.snapshot(self.now_ms())
        white_elo = db.get_elo(self.db_conn, self.game_state.white_name)
        black_elo = db.get_elo(self.db_conn, self.game_state.black_name)
        return StateUpdate(
            board=snapshot["board"],
            white_name=self.game_state.white_name,
            black_name=self.game_state.black_name,
            white_elo=white_elo,
            black_elo=black_elo,
            score_w=snapshot["score"]["w"],
            score_b=snapshot["score"]["b"],
            turn=self.game_state.current_turn,
            game_over=snapshot["game_over"],
        )

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
            self.session.tick(self.now_ms())

    async def dispatch_broadcasts(self) -> None:
        """Broadcasts driven by the bus: fires when GameSession actually
        publishes move_logged/score_changed/game_over, not on a blind timer."""
        while True:
            event_type, _payload = await self._broadcast_queue.get()
            logger.info("bus event %s -> broadcasting state", event_type)
            if event_type == "game_over":
                self._apply_elo_update()
            await self._broadcast_state()
