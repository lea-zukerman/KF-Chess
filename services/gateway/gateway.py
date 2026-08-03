"""Gateway: the WebSocket endpoint players connect to.

Authenticates them, pairs them via Matchmaker or by room id, and then opens a
connection to the shard running their game and relays between the two. It runs
no game logic: once the relay starts, this process only copies messages, and
every rule stays in the shard's GameEngine.
"""

import argparse
import asyncio
import logging

import os

import redis.asyncio
import websockets

from protocol.messages import AllocateRequest, AuthError, LoggedIn, LoginRequest, MatchLocation

from server import db
from server.matchmaking import Matchmaker
from server.rooms import RoomManager
from transport.connection import Connection, ConnectionClosed

from . import lobby

logger = logging.getLogger(__name__)

AUTH_EXPECTED_LOGIN = "EXPECTED_LOGIN"
AUTH_INVALID_CREDENTIALS = "INVALID_CREDENTIALS"

DEFAULT_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
# No shard is named here on purpose: which one runs a game is the
# allocator's call, not configuration. See Server_Design.md section 3.3.
DEFAULT_ALLOCATOR_HOST = os.environ.get("ALLOCATOR_HOST", "localhost")
DEFAULT_ALLOCATOR_PORT = int(os.environ.get("ALLOCATOR_PORT", "8767"))


class ShardUnavailable(Exception):
    """The allocator did not answer with a location."""


class GameServer:
    """Gateway: login, matchmaking and rooms. Runs no games itself -- once a
    player has an opponent it opens a connection to a shard and relays."""

    def __init__(
        self,
        db_url: str = db.DEFAULT_DB_URL,
        redis_client=None,
        allocator_host: str = DEFAULT_ALLOCATOR_HOST,
        allocator_port: int = DEFAULT_ALLOCATOR_PORT,
    ):
        self.db_conn = db.init_db(db_url)
        # Injected by the tests; built from the environment when running for
        # real. Connecting is lazy, so nothing happens until a room is used.
        self.redis = (
            redis_client
            if redis_client is not None
            else redis.asyncio.from_url(DEFAULT_REDIS_URL, decode_responses=True)
        )
        self.matchmaker = Matchmaker(self.redis)
        self.room_manager = RoomManager(self.db_conn, self.redis)
        self.allocator_host = allocator_host
        self.allocator_port = allocator_port

    async def locate_shard(self, white: str, black: str) -> tuple[str, int]:
        """Ask the allocator where this pair's game runs.

        A fresh connection per ask: this happens once per player per game,
        not per move, so pooling would be complexity without a matching cost.
        """
        allocator = await Connection.connect(self.allocator_host, self.allocator_port)
        try:
            await allocator.send(AllocateRequest(white, black))
            reply = await allocator.receive()
        finally:
            await allocator.close()

        if not isinstance(reply, MatchLocation):
            raise ShardUnavailable(f"allocator replied {reply!r}")
        return reply.host, reply.port

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
        ends once a handler has relayed the connection to a shard."""
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
