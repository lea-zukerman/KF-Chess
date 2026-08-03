"""Room-based pairing: players join a game by sharing a short room id
instead of by ELO. Independent of server/matchmaking.py -- the "Play" button
pairs strangers within an ELO range; "Room" pairs people who already know
each other and deliberately ignores rating.

Everything a room needs lives in Redis, so a creator waiting on one gateway
is woken by a joiner who arrived at a different one. That is the point of
stage 3: the earlier version kept the Match and an asyncio.Event in this
process, which silently required both players to land on the same one.

This module names players; it never builds a Match. Deciding who plays is a
gateway's job and running the game is a shard's, which is what let the Match
leave this file entirely.
"""

from __future__ import annotations

import secrets

ROOM_ID_LENGTH = 4
# uppercase letters + digits, minus visually ambiguous 0/O/1/I/L
ROOM_ID_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

ROOM_KEY_PREFIX = "room:"
JOINED_KEY_SUFFIX = ":joined"
# An abandoned room disappears on its own rather than through cleanup code.
ROOM_TTL_SECONDS = 3600
# Only ever hit if two processes draw the same id in the same instant.
ROOM_ID_ATTEMPTS = 10


class RoomNotFound(Exception):
    pass


class RoomIdUnavailable(Exception):
    """Every generated id collided -- effectively impossible, but not silent."""


class RoomAbandoned(Exception):
    """Nobody joined before the creator's wait ran out."""


class RoomManager:
    """Registry of open rooms, keyed by room id. Mirrors Matchmaker's role
    for the "Play" flow, but pairs by shared id rather than by ELO."""

    def __init__(self, redis):
        self.redis = redis

    async def create_room(self, creator_username: str) -> str:
        """Register a pending room and return its id. Does not block -- the
        creator sends itself into wait_for_opponent() afterwards, so the id
        can be shown before anyone has joined."""
        for _ in range(ROOM_ID_ATTEMPTS):
            room_id = "".join(
                secrets.choice(ROOM_ID_ALPHABET) for _ in range(ROOM_ID_LENGTH)
            )
            key = ROOM_KEY_PREFIX + room_id
            # hsetnx writes only if the field is free. One atomic operation
            # replaces both the "is this id taken?" check and the lock that
            # used to guard it -- two processes drawing the same id cannot
            # both win.
            if await self.redis.hsetnx(key, "creator", creator_username):
                await self.redis.expire(key, ROOM_TTL_SECONDS)
                return room_id

        raise RoomIdUnavailable()

    async def wait_for_opponent(
        self, room_id: str, timeout: int = ROOM_TTL_SECONDS
    ) -> str:
        """Block until someone joins, and return their username.

        blpop rather than an asyncio.Event: the joiner may well be talking to
        a different gateway process, and an Event only exists in one of them.
        """
        popped = await self.redis.blpop(
            ROOM_KEY_PREFIX + room_id + JOINED_KEY_SUFFIX, timeout=timeout
        )
        if popped is None:
            raise RoomAbandoned(room_id)
        _key, joiner_username = popped
        return joiner_username

    async def join_room(self, room_id: str, joiner_username: str) -> tuple[str, str, str]:
        """Join an existing room; returns (white, black, role).

        The first joiner takes the black seat and wakes the creator. Later
        joiners find the seat taken and become observers on the same pair.
        Raises RoomNotFound for an unknown id.
        """
        key = ROOM_KEY_PREFIX + room_id
        creator_username = await self.redis.hget(key, "creator")
        if creator_username is None:
            raise RoomNotFound(room_id)

        if await self.redis.hsetnx(key, "black", joiner_username):
            joined_key = key + JOINED_KEY_SUFFIX
            await self.redis.rpush(joined_key, joiner_username)
            await self.redis.expire(joined_key, ROOM_TTL_SECONDS)
            return creator_username, joiner_username, "b"

        black_username = await self.redis.hget(key, "black")
        return creator_username, black_username, "observer"
