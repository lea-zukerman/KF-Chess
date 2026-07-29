"""Room-based pairing: players join a game by sharing a short room id
instead of by ELO. Independent of server/matchmaking.py -- the "Play" button
pairs strangers within an ELO range; "Room" pairs people who already know
each other and deliberately ignores rating.

Create registers a new room id (creator = white) and returns immediately so
the id can be shown to the creator. The first Join on that id becomes black
and, at that moment -- now that both usernames are known -- the Match is
created and the waiting creator is woken. Further joins on the same id become
observers on the existing Match.

The registry of open rooms lives in Redis so that every server process sees
the same rooms. The live Match and the event that wakes its creator stay in
this process: they are Python objects, and moving them out is what stage 3
of Server_Design.md does, when a room id resolves to a shard address instead.
"""

from __future__ import annotations

import asyncio
import json
import secrets

from .match import Match

ROOM_ID_LENGTH = 4
# uppercase letters + digits, minus visually ambiguous 0/O/1/I/L
ROOM_ID_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

ROOM_KEY_PREFIX = "room:"
# An abandoned room disappears on its own rather than through cleanup code.
ROOM_TTL_SECONDS = 3600
# Only ever hit if two processes draw the same id in the same instant.
ROOM_ID_ATTEMPTS = 10


class RoomNotFound(Exception):
    pass


class RoomIdUnavailable(Exception):
    """Every generated id collided -- effectively impossible, but not silent."""


class _LiveRoom:
    """The half of a room that cannot leave this process: the running Match
    and the event the blocked creator is waiting on."""

    def __init__(self):
        self.match: Match | None = None
        self.ready = asyncio.Event()


class RoomManager:
    """Registry of open/active rooms, keyed by room id. Mirrors Matchmaker's
    role for the "Play" flow, but pairs by shared id rather than by ELO."""

    def __init__(self, db_conn, redis):
        self.db_conn = db_conn
        self.redis = redis
        self._live: dict[str, _LiveRoom] = {}

    async def create_room(self, creator_username: str) -> str:
        """Register a pending room and return its id. Does not block -- the
        creator sends itself into wait_for_match() afterwards."""
        record = json.dumps({"creator": creator_username})

        for _ in range(ROOM_ID_ATTEMPTS):
            room_id = "".join(
                secrets.choice(ROOM_ID_ALPHABET) for _ in range(ROOM_ID_LENGTH)
            )
            # nx: write only if the id is free. One atomic operation replaces
            # both the "is it taken?" check and the lock that used to guard it
            # -- two processes drawing the same id cannot both win.
            claimed = await self.redis.set(
                ROOM_KEY_PREFIX + room_id, record, nx=True, ex=ROOM_TTL_SECONDS
            )
            if claimed:
                self._live[room_id] = _LiveRoom()
                return room_id

        raise RoomIdUnavailable()

    async def wait_for_match(self, room_id: str) -> Match:
        """Block until someone joins the room and its Match is created."""
        live = self._live[room_id]
        await live.ready.wait()
        return live.match

    async def join_room(self, room_id: str, joiner_username: str) -> tuple[Match, str]:
        """Join an existing room. Raises RoomNotFound for an unknown id.

        The first joiner creates the Match (both usernames now known),
        becomes 'b', and wakes the creator. Later joiners get 'observer'
        on the same Match.
        """
        raw = await self.redis.get(ROOM_KEY_PREFIX + room_id)
        if raw is None:
            raise RoomNotFound(room_id)

        creator_username = json.loads(raw)["creator"]
        live = self._live[room_id]

        if live.match is None:
            live.match = Match(creator_username, joiner_username, self.db_conn)
            live.match.start()
            live.ready.set()
            return live.match, "b"

        return live.match, "observer"
