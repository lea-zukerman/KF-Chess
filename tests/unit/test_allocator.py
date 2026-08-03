import asyncio
import unittest

import fakeredis.aioredis

from services.allocator.allocator import Allocator, parse_shards


class ParseShardsTests(unittest.TestCase):
    def test_parses_a_comma_separated_list(self):
        self.assertEqual(
            parse_shards("shard-1:8766,shard-2:8766"),
            [("shard-1", 8766), ("shard-2", 8766)],
        )

    def test_ignores_blank_entries_and_whitespace(self):
        self.assertEqual(parse_shards(" a:1 , , b:2 "), [("a", 1), ("b", 2)])


class AllocatorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Implements real Redis semantics (nx, ex, incr) in memory, so these
        # stay honest tests without needing a Redis process.
        self.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        self.shards = [("shard-1", 8766), ("shard-2", 8766)]
        self.allocator = Allocator(self.redis, self.shards)

    def test_rejects_an_empty_fleet(self):
        """Better here than as an IndexError on the first player to click Play."""
        with self.assertRaises(ValueError):
            Allocator(self.redis, [])

    async def test_the_same_pair_always_gets_the_same_shard(self):
        first = await self.allocator.place("Alice", "Bob")
        second = await self.allocator.place("Alice", "Bob")

        self.assertEqual(first, second)

    async def test_concurrent_requests_for_one_pair_agree(self):
        """The real race: both gateways ask at the same instant. Exactly one
        write wins, and the loser must read the winner's answer back rather
        than keep the candidate it drew for itself."""
        results = await asyncio.gather(
            *(self.allocator.place("Alice", "Bob") for _ in range(8))
        )

        self.assertEqual(len(set(results)), 1)

    async def test_different_pairs_spread_across_the_fleet(self):
        first = await self.allocator.place("Alice", "Bob")
        second = await self.allocator.place("Carol", "Dave")

        self.assertNotEqual(first, second)
        self.assertEqual({first, second}, set(self.shards))

    async def test_a_placement_is_one_of_the_configured_shards(self):
        placement = await self.allocator.place("Alice", "Bob")

        self.assertIn(placement, self.shards)


if __name__ == "__main__":
    unittest.main()
