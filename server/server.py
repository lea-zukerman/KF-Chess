"""Single-process WebSocket lobby: authenticates players, pairs them via
Matchmaker, then hands each connection off to a Match for the actual game.
Multiple Match instances can be alive at once, one per matched pair."""

import argparse
import asyncio
import logging

import websockets

from protocol.messages import AuthError, ErrorMessage, LoggedIn, LoginRequest, PlayRequest, SearchingForOpponent

from . import db
from .connection import Connection, ConnectionClosed
from .match import Match
from .matchmaking import Matchmaker, NoOpponentFound

logger = logging.getLogger(__name__)

AUTH_EXPECTED_LOGIN = "EXPECTED_LOGIN"
AUTH_INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
FLOW_EXPECTED_PLAY = "EXPECTED_PLAY"
FLOW_NO_OPPONENT_FOUND = "NO_OPPONENT_FOUND"


class GameServer:
    """Lobby: login + matchmaking. Creates one Match per matched pair."""

    def __init__(self, db_path: str = db.DEFAULT_DB_PATH):
        self.db_conn = db.init_db(db_path)
        self.matchmaker = Matchmaker()
        self._pending_matches: dict[tuple[str, str], Match] = {}
        self._match_lock = asyncio.Lock()

    async def handle_client(self, websocket) -> None:
        connection = Connection(websocket)
        username = await self._login(connection)
        if username is None:
            return

        if not await self._wait_for_play(connection):
            return

        await self._enter_matchmaking(connection, username)

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

    async def _wait_for_play(self, connection: Connection) -> bool:
        try:
            async for message in connection:
                if isinstance(message, PlayRequest):
                    return True
                await connection.send(ErrorMessage(FLOW_EXPECTED_PLAY))
        except ConnectionClosed:
            pass
        return False

    async def _enter_matchmaking(self, connection: Connection, username: str) -> None:
        elo_rating = db.get_elo(self.db_conn, username)
        await connection.send(SearchingForOpponent())
        logger.info("client '%s' (elo %d) entered matchmaking", username, elo_rating)

        try:
            opponent_username, _opponent_elo = await self.matchmaker.find_match(username, elo_rating)
        except NoOpponentFound:
            await connection.send(ErrorMessage(FLOW_NO_OPPONENT_FOUND))
            await connection.close()
            return

        white_username, black_username = sorted((username, opponent_username))
        match = await self._get_or_create_match(white_username, black_username)
        role = "w" if username == white_username else "b"
        logger.info("client '%s' matched with '%s' as %s", username, opponent_username, role)
        await match.join(connection, role)

    async def _get_or_create_match(self, white_username: str, black_username: str) -> Match:
        """Both matched players independently compute the same (white, black)
        key and arrive here separately -- the first to arrive creates the
        Match, the second finds it waiting and consumes the pending entry."""
        key = (white_username, black_username)
        async with self._match_lock:
            match = self._pending_matches.get(key)
            if match is None:
                match = Match(white_username, black_username, self.db_conn)
                match.start()
                self._pending_matches[key] = match
            else:
                del self._pending_matches[key]
        return match


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
