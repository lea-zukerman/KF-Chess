"""Single-process WebSocket lobby: authenticates players, pairs them via
Matchmaker, then hands each connection off to a Match for the actual game.
Multiple Match instances can be alive at once, one per matched pair."""

import argparse
import asyncio
import logging

import os

import redis.asyncio
import websockets

from protocol.messages import AuthError, LoggedIn, LoginRequest

from . import db, lobby
from transport.connection import Connection, ConnectionClosed
from .match import Match
from .matchmaking import Matchmaker
from .rooms import RoomManager

logger = logging.getLogger(__name__)

AUTH_EXPECTED_LOGIN = "EXPECTED_LOGIN"
AUTH_INVALID_CREDENTIALS = "INVALID_CREDENTIALS"

DEFAULT_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")


class GameServer:
    """Lobby: login + matchmaking. Creates one Match per matched pair."""

    def __init__(self, db_url: str = db.DEFAULT_DB_URL, redis_client=None):
        self.db_conn = db.init_db(db_url)
        # Injected by the tests; built from the environment when running for
        # real. Connecting is lazy, so nothing happens until a room is used.
        self.redis = (
            redis_client
            if redis_client is not None
            else redis.asyncio.from_url(DEFAULT_REDIS_URL)
        )
        self.matchmaker = Matchmaker()
        self.room_manager = RoomManager(self.db_conn, self.redis)
        self._pending_matches: dict[tuple[str, str], Match] = {}
        self._match_lock = asyncio.Lock()

    async def handle_client(self, websocket) -> None:
        connection = Connection(websocket)
        username = await self._login(connection)
        if username is None:
            return

        await self._home_screen(connection, username)

    async def _login(self, connection: Connection) -> str | None:
        try:
            message = await connection.receive()
        except ConnectionClosed:
            return None

        if not isinstance(message, LoginRequest):
            await connection.send(AuthError(AUTH_EXPECTED_LOGIN))
            await connection.close()
            return None

        if not db.authenticate_or_register(self.db_conn, message.username, message.password):
            await connection.send(AuthError(AUTH_INVALID_CREDENTIALS))
            await connection.close()
            return None

        logger.info("client '%s' logged in", message.username)
        await connection.send(LoggedIn())
        return message.username

    async def _home_screen(self, connection: Connection, username: str) -> None:
        """Post-login lobby: read home-screen commands and let lobby.dispatch
        route each one. This loop knows nothing about Play vs Room -- it just
        ends once a handler has handed the connection off to a Match."""
        try:
            async for message in connection:
                if await lobby.dispatch(self, connection, username, message):
                    return
        except ConnectionClosed:
            pass


async def run_server(host: str = "localhost", port: int = 8765) -> None:
    server = GameServer()
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
