import asyncio
import unittest

import fakeredis.aioredis

from server import db
from server.match import Match
from server.rooms import ROOM_ID_ALPHABET, ROOM_ID_LENGTH, RoomManager, RoomNotFound


class RoomManagerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db_conn = db.init_db(":memory:")
        db.authenticate_or_register(self.db_conn, "Alice", "pass123")
        db.authenticate_or_register(self.db_conn, "Bob", "pass123")
        db.authenticate_or_register(self.db_conn, "Carol", "pass123")
        # Implements real Redis semantics (nx, ex, sorted sets) in memory,
        # so these stay honest tests without needing a Redis process.
        self.manager = RoomManager(self.db_conn, fakeredis.aioredis.FakeRedis(decode_responses=True))

    async def test_create_room_returns_id_from_allowed_alphabet(self):
        room_id = await self.manager.create_room("Alice")

        self.assertEqual(len(room_id), ROOM_ID_LENGTH)
        self.assertTrue(all(char in ROOM_ID_ALPHABET for char in room_id))

    async def test_two_rooms_get_distinct_ids(self):
        first = await self.manager.create_room("Alice")
        second = await self.manager.create_room("Bob")

        self.assertNotEqual(first, second)

    async def test_join_unknown_room_raises(self):
        with self.assertRaises(RoomNotFound):
            await self.manager.join_room("ZZZZ", "Bob")

    async def test_first_joiner_becomes_black_and_creates_the_match(self):
        room_id = await self.manager.create_room("Alice")

        match, role = await self.manager.join_room(room_id, "Bob")
        self.addCleanup(match.stop)

        self.assertEqual(role, "b")
        self.assertIsInstance(match, Match)
        self.assertEqual(match.game_state.white_name, "Alice")
        self.assertEqual(match.game_state.black_name, "Bob")

    async def test_waiting_creator_receives_the_same_match(self):
        room_id = await self.manager.create_room("Alice")
        waiter = asyncio.ensure_future(self.manager.wait_for_match(room_id))

        joined_match, _role = await self.manager.join_room(room_id, "Bob")
        self.addCleanup(joined_match.stop)

        creator_match = await asyncio.wait_for(waiter, timeout=1)
        self.assertIs(creator_match, joined_match)

    async def test_third_person_becomes_observer_on_the_same_match(self):
        room_id = await self.manager.create_room("Alice")

        first_match, first_role = await self.manager.join_room(room_id, "Bob")
        self.addCleanup(first_match.stop)
        second_match, second_role = await self.manager.join_room(room_id, "Carol")

        self.assertEqual(first_role, "b")
        self.assertEqual(second_role, "observer")
        self.assertIs(second_match, first_match)


if __name__ == "__main__":
    unittest.main()
