import asyncio
import unittest
from unittest import mock

from server import matchmaking


class MatchmakerTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_compatible_players_are_matched(self):
        mm = matchmaking.Matchmaker()

        alice_task = asyncio.create_task(mm.find_match("alice", 1200))
        await asyncio.sleep(0)  # let alice start waiting

        bob_result = await mm.find_match("bob", 1250)
        alice_result = await alice_task

        self.assertEqual(alice_result, ("bob", 1250))
        self.assertEqual(bob_result, ("alice", 1200))
        self.assertEqual(mm._waiting, [])

    async def test_out_of_range_elo_does_not_match_and_both_time_out(self):
        mm = matchmaking.Matchmaker()
        with mock.patch.object(matchmaking, "MATCH_TIMEOUT_SECONDS", 0.05):
            alice_task = asyncio.create_task(mm.find_match("alice", 1200))
            await asyncio.sleep(0)

            with self.assertRaises(matchmaking.NoOpponentFound):
                await mm.find_match("carol", 1400)

            with self.assertRaises(matchmaking.NoOpponentFound):
                await alice_task

        self.assertEqual(mm._waiting, [])

    async def test_lone_waiter_times_out_and_is_removed_from_pool(self):
        mm = matchmaking.Matchmaker()
        with mock.patch.object(matchmaking, "MATCH_TIMEOUT_SECONDS", 0.05):
            with self.assertRaises(matchmaking.NoOpponentFound):
                await mm.find_match("alice", 1200)

        self.assertEqual(mm._waiting, [])

    async def test_cancelled_wait_is_removed_from_pool(self):
        mm = matchmaking.Matchmaker()
        with mock.patch.object(matchmaking, "MATCH_TIMEOUT_SECONDS", 5):
            task = asyncio.create_task(mm.find_match("alice", 1200))
            await asyncio.sleep(0)
            task.cancel()

            with self.assertRaises(asyncio.CancelledError):
                await task

        self.assertEqual(mm._waiting, [])


if __name__ == '__main__':
    unittest.main()
