"""Game Allocator: decides which shard runs a given match.

The Matchmaker and the Rooms API decide *who* plays whom; this decides
*where* it runs. Keeping the two apart is what lets the fleet grow without
constraining who can play against whom -- Server_Design.md section 3.3.

The decision is made once per pair and remembered in Redis, because the two
gateways holding the two players ask separately and must get the same
answer. Whoever writes first wins; the loser reads the winner's value back
instead of keeping its own candidate.

What this does not do yet: notice that a shard is down, or weigh load. Both
need shards reporting on the event bus, which is stage 4. Until then a
stale placement pointing at a dead shard shows up as a failed connect from
the gateway, and section 10.3 already settled that such a game is dropped
rather than moved.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os

import redis.asyncio
import websockets

from protocol.messages import AllocateRequest, MatchLocation
from transport.connection import Connection, ConnectionClosed

logger = logging.getLogger(__name__)

DEFAULT_PORT = 8767
DEFAULT_SHARDS = os.environ.get("SHARDS", "localhost:8766")
DEFAULT_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")

PLACEMENT_KEY_PREFIX = "alloc:"
ROUND_ROBIN_KEY = "alloc:rr"
# Generous next to a 30-90 second game (section 9.1). The margin is for an
# observer joining a room long after its game started.
PLACEMENT_TTL_SECONDS = 1800


def parse_shards(raw: str) -> list[tuple[str, int]]:
    """"host:port,host:port" -> [(host, port), ...]"""
    shards = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        host, _, port = entry.rpartition(":")
        shards.append((host, int(port)))
    return shards


def _parse_address(raw: str) -> tuple[str, int]:
    host, _, port = raw.rpartition(":")
    return host, int(port)


class Allocator:
    def __init__(self, redis, shards: list[tuple[str, int]]):
        # Better here than as an IndexError on the first player to click Play.
        if not shards:
            raise ValueError("allocator needs at least one shard")
        self.redis = redis
        self.shards = shards

    async def place(self, white: str, black: str) -> tuple[str, int]:
        """The shard for this pair, chosen now or recalled from an earlier ask."""
        key = f"{PLACEMENT_KEY_PREFIX}{white}:{black}"

        # Read before drawing a candidate, so a pair that is already placed
        # does not burn a slot in the rotation and skew the spread.
        existing = await self.redis.get(key)
        if existing is not None:
            return _parse_address(existing)

        candidate = await self._next_shard()
        claimed = await self.redis.set(
            key, f"{candidate[0]}:{candidate[1]}", nx=True, ex=PLACEMENT_TTL_SECONDS
        )
        if claimed:
            logger.info("placed %s vs %s on %s:%d", white, black, *candidate)
            return candidate

        # Someone wrote between our read and our write. Their answer is the
        # one the other gateway is already acting on, so it wins.
        raw = await self.redis.get(key)
        return _parse_address(raw) if raw else candidate

    async def _next_shard(self) -> tuple[str, int]:
        """Round-robin. The counter lives in Redis so several allocator
        instances keep sharing one rotation instead of each starting over."""
        index = await self.redis.incr(ROUND_ROBIN_KEY)
        return self.shards[(index - 1) % len(self.shards)]

    async def handle_gateway(self, websocket) -> None:
        """One gateway's questions. Kept open for the length of its ask; a
        gateway opens this once per player entering a game, not per move."""
        connection = Connection(websocket)
        try:
            async for message in connection:
                if not isinstance(message, AllocateRequest):
                    logger.warning("ignoring %r, expected AllocateRequest", message)
                    continue
                host, port = await self.place(message.white, message.black)
                await connection.send(MatchLocation(host, port))
        except ConnectionClosed:
            pass


async def run_allocator(host: str = "0.0.0.0", port: int = DEFAULT_PORT) -> None:
    allocator = Allocator(
        redis.asyncio.from_url(DEFAULT_REDIS_URL, decode_responses=True),
        parse_shards(DEFAULT_SHARDS),
    )
    async with websockets.serve(allocator.handle_gateway, host, port):
        logger.info("allocator listening on %s:%d, fleet=%s", host, port, allocator.shards)
        await asyncio.Future()  # run forever


def main() -> None:
    parser = argparse.ArgumentParser(description="Kung Fu Chess game allocator")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(run_allocator(args.host, args.port))


if __name__ == "__main__":
    main()
