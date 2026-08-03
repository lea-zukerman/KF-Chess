"""Game server shard: runs matches, and nothing else.

A shard has no idea who is logged in, who is looking for a game, or which
rooms exist. A gateway has already decided who plays whom and connects here
once per player, opening with an AttachToMatch naming the pair and the role.
Both gateways derive the same (white, black) pair independently, which is what
lets two separate connections meet on one Match without the shard coordinating
anything.

Matches are keyed by that pair and live until their last client leaves, so a
third connection on the same pair joins the running game as an observer
instead of starting a second one.
"""

import argparse
import asyncio
import logging

import websockets

from protocol.messages import AttachToMatch
from transport.connection import Connection, ConnectionClosed

from server import db
from server.match import Match

logger = logging.getLogger(__name__)

DEFAULT_PORT = 8766


class Shard:
    """Holds the Matches running on this process, keyed by (white, black)."""

    def __init__(self, db_url: str = db.DEFAULT_DB_URL):
        self.db_conn = db.init_db(db_url)
        self._matches: dict[tuple[str, str], Match] = {}
        self._lock = asyncio.Lock()

    async def handle_gateway(self, websocket) -> None:
        """One connection from a gateway, carrying one player (or observer)."""
        connection = Connection(websocket)
        try:
            message = await connection.receive()
        except ConnectionClosed:
            return

        if not isinstance(message, AttachToMatch):
            logger.warning("first message was %r, not AttachToMatch", message)
            await connection.close()
            return

        key = (message.white, message.black)
        match = await self._acquire(key)
        try:
            await match.join(connection, message.role)
        finally:
            await self._release(key, match)

    async def _acquire(self, key: tuple[str, str]) -> Match:
        """The Match for this pair, started if this is the first arrival."""
        async with self._lock:
            match = self._matches.get(key)
            if match is None:
                match = Match(key[0], key[1], self.db_conn)
                match.start()
                self._matches[key] = match
                logger.info("match %s vs %s started (live=%d)", *key, len(self._matches))
            return match

    async def _release(self, key: tuple[str, str], match: Match) -> None:
        """Drop the Match once nobody is attached to it.

        Deliberately not "once the second player has arrived", which is what
        the lobby did: that leaves a third connection on the same pair to
        create a whole new game instead of joining the running one.
        """
        async with self._lock:
            if match.clients:
                return
            if self._matches.get(key) is match:
                match.stop()
                del self._matches[key]
                logger.info("match %s vs %s ended (live=%d)", *key, len(self._matches))


async def run_shard(host: str = "0.0.0.0", port: int = DEFAULT_PORT) -> None:
    shard = Shard()
    async with websockets.serve(shard.handle_gateway, host, port):
        logger.info("shard listening on %s:%d", host, port)
        await asyncio.Future()  # run forever


def main() -> None:
    parser = argparse.ArgumentParser(description="Kung Fu Chess game server shard")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(run_shard(args.host, args.port))


if __name__ == "__main__":
    main()
