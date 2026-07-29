import asyncio
import time
import unittest
from unittest import mock

import fakeredis.aioredis

from server import matchmaking


class MatchmakerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        self.mm = matchmaking.Matchmaker(self.redis)

    async def _queued(self) -> list[str]:
        return await self.redis.zrange(matchmaking.WAITING_BY_ELO, 0, -1)

    async def _wait_until_queued(self, username: str) -> None:
        """Joining the pool now takes several awaits, so yielding once is not
        enough to know the waiter is actually in it."""
        for _ in range(100):
            if username in await self._queued():
                return
            await asyncio.sleep(0.01)
        self.fail(f"{username} never joined the waiting pool")

    async def test_two_compatible_players_are_matched(self):
        alice_task = asyncio.create_task(self.mm.find_match("alice", 1200))
        await self._wait_until_queued("alice")

        bob_result = await self.mm.find_match("bob", 1250)
        alice_result = await alice_task

        self.assertEqual(alice_result, ("bob", 1250))
        self.assertEqual(bob_result, ("alice", 1200))
        self.assertEqual(self.mm._waiting, {})
        self.assertEqual(await self._queued(), [])

    async def test_out_of_range_elo_does_not_match_and_both_time_out(self):
        with mock.patch.object(matchmaking, "MATCH_TIMEOUT_SECONDS", 0.05):
            alice_task = asyncio.create_task(self.mm.find_match("alice", 1200))
            await self._wait_until_queued("alice")

            with self.assertRaises(matchmaking.NoOpponentFound):
                await self.mm.find_match("carol", 1400)

            with self.assertRaises(matchmaking.NoOpponentFound):
                await alice_task

        self.assertEqual(self.mm._waiting, {})
        self.assertEqual(await self._queued(), [])

    async def test_lone_waiter_times_out_and_is_removed_from_pool(self):
        with mock.patch.object(matchmaking, "MATCH_TIMEOUT_SECONDS", 0.05):
            with self.assertRaises(matchmaking.NoOpponentFound):
                await self.mm.find_match("alice", 1200)

        self.assertEqual(self.mm._waiting, {})
        self.assertEqual(await self._queued(), [])

    async def test_cancelled_wait_is_removed_from_pool(self):
        with mock.patch.object(matchmaking, "MATCH_TIMEOUT_SECONDS", 5):
            task = asyncio.create_task(self.mm.find_match("alice", 1200))
            await self._wait_until_queued("alice")
            task.cancel()

            with self.assertRaises(asyncio.CancelledError):
                await task

        self.assertEqual(self.mm._waiting, {})
        self.assertEqual(await self._queued(), [])

    async def test_a_stale_entry_left_by_a_dead_process_is_dropped(self):
        """Nothing removed this one -- no coroutine is waiting on it. It is
        what a server killed mid-wait leaves behind, and the next call by any
        process has to clear it."""
        await self.redis.zadd(matchmaking.WAITING_BY_ELO, {"ghost": 1200})
        await self.redis.zadd(
            matchmaking.WAITING_BY_TIME,
            {"ghost": time.time() - matchmaking.MATCH_TIMEOUT_SECONDS - 1},
        )

        with mock.patch.object(matchmaking, "MATCH_TIMEOUT_SECONDS", 0.05):
            with self.assertRaises(matchmaking.NoOpponentFound):
                await self.mm.find_match("alice", 1200)

        self.assertEqual(await self._queued(), [])

    async def test_a_fresh_entry_is_not_dropped(self):
        await self.redis.zadd(matchmaking.WAITING_BY_ELO, {"bob": 1200})
        await self.redis.zadd(matchmaking.WAITING_BY_TIME, {"bob": time.time()})

        # bob has no coroutine waiting, so alice claims him and gets nothing
        # back to wake -- but he must be claimed rather than expired.
        opponent = await self.mm._claim_opponent("alice", 1200)

        self.assertEqual(opponent, ("bob", 1200))


if __name__ == "__main__":
    unittest.main()
