import asyncio
import unittest

import fakeredis.aioredis

from server.rooms import (
    ROOM_ID_ALPHABET,
    ROOM_ID_LENGTH,
    RoomAbandoned,
    RoomManager,
    RoomNotFound,
)


class RoomManagerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Implements real Redis semantics (hsetnx, blpop, expire) in memory,
        # so these stay honest tests without needing a Redis process.
        self.manager = RoomManager(fakeredis.aioredis.FakeRedis(decode_responses=True))

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

    async def test_first_joiner_becomes_black(self):
        room_id = await self.manager.create_room("Alice")

        white, black, role = await self.manager.join_room(room_id, "Bob")

        self.assertEqual((white, black, role), ("Alice", "Bob", "b"))

    async def test_third_person_becomes_observer_on_the_same_pair(self):
        room_id = await self.manager.create_room("Alice")
        await self.manager.join_room(room_id, "Bob")

        white, black, role = await self.manager.join_room(room_id, "Carol")

        self.assertEqual((white, black, role), ("Alice", "Bob", "observer"))

    async def test_waiting_creator_learns_the_joiner(self):
        room_id = await self.manager.create_room("Alice")
        waiter = asyncio.ensure_future(self.manager.wait_for_opponent(room_id))
        await asyncio.sleep(0)  # let the waiter reach its blpop

        await self.manager.join_room(room_id, "Bob")

        self.assertEqual(await asyncio.wait_for(waiter, timeout=2), "Bob")

    async def test_two_joiners_cannot_both_be_black(self):
        """The cross-process race: hsetnx decides it, not a lock. Two people
        typing the same room id at once must not both get the black seat."""
        room_id = await self.manager.create_room("Alice")

        results = await asyncio.gather(
            self.manager.join_room(room_id, "Bob"),
            self.manager.join_room(room_id, "Carol"),
        )

        roles = sorted(role for _white, _black, role in results)
        self.assertEqual(roles, ["b", "observer"])

    async def test_a_room_nobody_joins_times_out(self):
        room_id = await self.manager.create_room("Alice")

        with self.assertRaises(RoomAbandoned):
            await self.manager.wait_for_opponent(room_id, timeout=1)


if __name__ == "__main__":
    unittest.main()
