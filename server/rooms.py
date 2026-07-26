"""Room-based pairing: players join a game by sharing a short room id
instead of by ELO. Independent of server/matchmaking.py -- the "Play" button
pairs strangers within an ELO range; "Room" pairs people who already know
each other and deliberately ignores rating.

Create registers a new room id (creator = white) and returns immediately so
the id can be shown to the creator. The first Join on that id becomes black
and, at that moment -- now that both usernames are known -- the Match is
created and the waiting creator is woken. Further joins on the same id become
observers on the existing Match.
"""

from __future__ import annotations

import asyncio
import secrets

from .match import Match

ROOM_ID_LENGTH = 4
# uppercase letters + digits, minus visually ambiguous 0/O/1/I/L
ROOM_ID_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


class RoomNotFound(Exception):
    pass


class _Room:
    """One room's state: the creator (white) and, once someone joins, the
    live Match. `ready` lets the blocked creator wait for that Match to exist.
    """

    def __init__(self, creator_username: str):
        self.creator_username = creator_username
        self.match: Match | None = None
        self.ready = asyncio.Event()


class RoomManager:
    """Registry of open/active rooms, keyed by room id. Mirrors Matchmaker's
    role for the "Play" flow, but pairs by shared id rather than by ELO."""

    def __init__(self, db_conn):
        self.db_conn = db_conn
        self._rooms: dict[str, _Room] = {}
        self._lock = asyncio.Lock()

    async def create_room(self, creator_username: str) -> str:
        """Register a pending room and return its id. Does not block -- the
        creator sends itself into wait_for_match() afterwards."""
        async with self._lock:
            room_id = self._generate_unique_id()
            self._rooms[room_id] = _Room(creator_username)
        return room_id

    async def wait_for_match(self, room_id: str) -> Match:
        """Block until someone joins the room and its Match is created."""
        room = self._rooms[room_id]
        await room.ready.wait()
        return room.match

    async def join_room(self, room_id: str, joiner_username: str) -> tuple[Match, str]:
        """Join an existing room. Raises RoomNotFound for an unknown id.

        The first joiner creates the Match (both usernames now known),
        becomes 'b', and wakes the creator. Later joiners get 'observer'
        on the same Match.
        """
        async with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                raise RoomNotFound(room_id)
            if room.match is None:
                room.match = Match(room.creator_username, joiner_username, self.db_conn)
                room.match.start()
                room.ready.set()
                return room.match, "b"
            return room.match, "observer"

    def _generate_unique_id(self) -> str:
        while True:
            room_id = "".join(secrets.choice(ROOM_ID_ALPHABET) for _ in range(ROOM_ID_LENGTH))
            if room_id not in self._rooms:
                return room_id
