import asyncio
import unittest
from unittest import mock

import websockets

from server import db
from server import match as match_module
from server.match import Match


class MatchTests(unittest.IsolatedAsyncioTestCase):
    async def _start_match(self, board_text=None):
        self.db_conn = db.init_db(":memory:")
        db.authenticate_or_register(self.db_conn, "Alice", "pass123")
        db.authenticate_or_register(self.db_conn, "Bob", "pass123")

        kwargs = {}
        if board_text is not None:
            kwargs["board_text"] = board_text
        self.match = Match("Alice", "Bob", self.db_conn, **kwargs)
        self.match.start()
        self.addCleanup(self.match.stop)

        roles = iter(["w", "b", "observer"])

        async def handler(websocket):
            role = next(roles)
            await self.match.join(websocket, role)

        ws_server = await websockets.serve(handler, "localhost", 0)
        self.addAsyncCleanup(ws_server.close)
        port = ws_server.sockets[0].getsockname()[1]
        return f"ws://localhost:{port}"

    async def test_white_and_black_get_their_roles_in_connection_order(self):
        uri = await self._start_match()

        async with websockets.connect(uri) as ws1:
            role1 = await ws1.recv()
            async with websockets.connect(uri) as ws2:
                role2 = await ws2.recv()

        self.assertEqual(role1, "role: w")
        self.assertEqual(role2, "role: b")

    async def test_existing_player_is_notified_when_the_other_joins(self):
        uri = await self._start_match()

        async with websockets.connect(uri) as ws1:
            await ws1.recv()  # role
            await ws1.recv()  # initial state (white only)

            async with websockets.connect(uri) as ws2:
                await ws2.recv()  # role

                notification = await ws1.recv()

        self.assertEqual(notification, "player_joined: b (Bob)")

    async def test_third_connection_is_observer_and_cannot_move(self):
        uri = await self._start_match()

        async with websockets.connect(uri) as ws1, \
                websockets.connect(uri) as ws2, \
                websockets.connect(uri) as ws3:
            await ws1.recv()  # role
            await ws2.recv()  # role
            self.assertEqual(await ws3.recv(), "role: observer")
            await ws3.recv()  # initial state broadcast

            await ws3.send("move e2 e4")
            reply = await ws3.recv()

        self.assertEqual(reply, "error: observers cannot move")

    async def test_black_cannot_move_before_white(self):
        uri = await self._start_match()

        async with websockets.connect(uri) as ws1, websockets.connect(uri) as ws2:
            await ws1.recv()  # role
            await ws1.recv()  # initial state
            await ws2.recv()  # role
            await ws2.recv()  # initial state

            await ws2.send("move e7 e5")
            reply = await ws2.recv()

        self.assertEqual(reply, "error: not your turn")

    async def test_malformed_command_replies_with_error_and_connection_stays_usable(self):
        uri = await self._start_match()

        async with websockets.connect(uri) as ws1:
            await ws1.recv()  # role
            await ws1.recv()  # initial state

            await ws1.send("teleport a1 h8")
            error_reply = await ws1.recv()

            await ws1.send("move e2 e4")
            move_reply = await ws1.recv()

        self.assertTrue(error_reply.startswith("error:"))
        self.assertTrue(move_reply.startswith("board:"))

    async def test_elo_changes_after_a_game_ends(self):
        uri = await self._start_match(board_text="bK .\nwR .")

        async with websockets.connect(uri) as ws1, websockets.connect(uri) as ws2:
            await ws1.recv()  # role
            await ws1.recv()  # initial state (white only)

            await ws2.recv()  # role
            await ws2.recv()  # broadcast after black joined
            await ws1.recv()  # player_joined notification
            await ws1.recv()  # broadcast after black joined

            await ws1.send("move a1 a2")
            await ws1.recv()  # move accepted, piece still traveling

            final_state = None
            for _ in range(10):
                message = await asyncio.wait_for(ws1.recv(), timeout=2)
                if "game_over: true" in message and "elo: w:1200 b:1200" not in message:
                    final_state = message
                    break

        self.assertIsNotNone(final_state)
        self.assertNotIn("elo: w:1200 b:1200", final_state)

    async def test_disconnect_during_a_game_triggers_countdown_then_auto_resigns(self):
        uri = await self._start_match()

        with mock.patch.object(match_module, "DISCONNECT_RESIGN_SECONDS", 2):
            ws1 = await websockets.connect(uri)
            await ws1.recv()  # role
            await ws1.recv()  # initial state

            async with websockets.connect(uri) as ws2:
                await ws2.recv()  # role
                await ws2.recv()  # broadcast after black joined
                await ws1.recv()  # player_joined notification
                await ws1.recv()  # broadcast after black joined

                await ws1.close()  # white disconnects mid-game

                countdown_2 = await asyncio.wait_for(ws2.recv(), timeout=2)
                countdown_1 = await asyncio.wait_for(ws2.recv(), timeout=2)
                final_state = await asyncio.wait_for(ws2.recv(), timeout=2)

        self.assertEqual(countdown_2, "resign_countdown: 2")
        self.assertEqual(countdown_1, "resign_countdown: 1")
        self.assertIn("game_over: true", final_state)
        self.assertIn("elo: w:1184 b:1216", final_state)
        self.assertEqual(db.get_elo(self.db_conn, "Alice"), 1184)
        self.assertEqual(db.get_elo(self.db_conn, "Bob"), 1216)


if __name__ == '__main__':
    unittest.main()
