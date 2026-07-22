"""Single-process WebSocket lobby: authenticates players, pairs them via
Matchmaker, then hands each connection off to a Match for the actual game.
Multiple Match instances can be alive at once, one per matched pair."""

import argparse
import asyncio
import logging

import websockets

from . import db
from .matchmaking import Matchmaker, NoOpponentFound
from .match import Match

logger = logging.getLogger(__name__)


class GameServer:
    """Lobby: login + matchmaking. Creates one Match per matched pair."""

    def __init__(self, db_path: str = db.DEFAULT_DB_PATH):
        self.db_conn = db.init_db(db_path)
        self.matchmaker = Matchmaker()
        self._pending_matches: dict[tuple[str, str], Match] = {}
        self._match_lock = asyncio.Lock()

    async def handle_client(self, websocket) -> None:
        username = await self._login(websocket)
        if username is None:
            return

        if not await self._wait_for_play(websocket):
            return

        await self._enter_matchmaking(websocket, username)

    async def _login(self, websocket) -> str | None:
        try:
            credentials = (await websocket.recv()).strip()
        except websockets.exceptions.ConnectionClosed:
            return None

        parts = credentials.split(maxsplit=2)
        if len(parts) != 3 or parts[0] != "login":
            await websocket.send("error: expected 'login <username> <password>'")
            await websocket.close()
            return None

        _, username, password = parts
        if not db.authenticate_or_register(self.db_conn, username, password):
            await websocket.send("error: bad credentials")
            await websocket.close()
            return None

        logger.info("client '%s' logged in", username)
        await websocket.send("logged_in: type 'play' to start matchmaking")
        return username

    async def _wait_for_play(self, websocket) -> bool:
        try:
            async for message in websocket:
                if message.strip() == "play":
                    return True
                await websocket.send("error: expected 'play'")
        except websockets.exceptions.ConnectionClosed:
            pass
        return False

    async def _enter_matchmaking(self, websocket, username: str) -> None:
        elo_rating = db.get_elo(self.db_conn, username)
        await websocket.send("searching_for_opponent")
        logger.info("client '%s' (elo %d) entered matchmaking", username, elo_rating)

        try:
            opponent_username, _opponent_elo = await self.matchmaker.find_match(username, elo_rating)
        except NoOpponentFound:
            await websocket.send("error: cannot find opponent")
            await websocket.close()
            return

        white_username, black_username = sorted((username, opponent_username))
        match = await self._get_or_create_match(white_username, black_username)
        role = "w" if username == white_username else "b"
        logger.info("client '%s' matched with '%s' as %s", username, opponent_username, role)
        await match.join(websocket, role)

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
