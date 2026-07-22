import asyncio
import unittest
from unittest import mock

import websockets

from server import db, matchmaking
from server.server import GameServer


class GameServerTests(unittest.IsolatedAsyncioTestCase):
    async def _start_server(self, db_path=":memory:"):
        server = GameServer(db_path=db_path)
        ws_server = await websockets.serve(server.handle_client, "localhost", 0)
        self.addAsyncCleanup(ws_server.close)
        port = ws_server.sockets[0].getsockname()[1]
        return server, f"ws://localhost:{port}"

    async def test_login_prompts_for_play(self):
        _, uri = await self._start_server()

        async with websockets.connect(uri) as ws:
            await ws.send("login Alice pass123")
            reply = await ws.recv()

        self.assertEqual(reply, "logged_in: type 'play' to start matchmaking")

    async def test_malformed_login_is_rejected(self):
        _, uri = await self._start_server()

        async with websockets.connect(uri) as ws:
            await ws.send("hello")
            reply = await ws.recv()

            with self.assertRaises(websockets.exceptions.ConnectionClosed):
                await ws.recv()

        self.assertEqual(reply, "error: expected 'login <username> <password>'")

    async def test_wrong_password_is_rejected_and_closes_the_connection(self):
        _, uri = await self._start_server()

        async with websockets.connect(uri) as ws1:
            await ws1.send("login Alice pass123")
            await ws1.recv()

        async with websockets.connect(uri) as ws2:
            await ws2.send("login Alice wrongpass")
            reply = await ws2.recv()

            with self.assertRaises(websockets.exceptions.ConnectionClosed):
                await ws2.recv()

        self.assertEqual(reply, "error: bad credentials")

    async def test_command_before_play_is_rejected_but_connection_stays_open(self):
        _, uri = await self._start_server()

        with mock.patch.object(matchmaking, "MATCH_TIMEOUT_SECONDS", 0.2):
            async with websockets.connect(uri) as ws:
                await ws.send("login Alice pass123")
                await ws.recv()  # logged_in

                await ws.send("status")
                error_reply = await ws.recv()

                await ws.send("play")
                searching_reply = await ws.recv()
                timeout_reply = await asyncio.wait_for(ws.recv(), timeout=2)

        self.assertEqual(error_reply, "error: expected 'play'")
        self.assertEqual(searching_reply, "searching_for_opponent")
        self.assertEqual(timeout_reply, "error: cannot find opponent")

    async def test_two_players_within_elo_range_are_matched_and_receive_roles(self):
        _, uri = await self._start_server()

        async with websockets.connect(uri) as ws1, websockets.connect(uri) as ws2:
            await ws1.send("login Alice pass123")
            await ws1.recv()  # logged_in
            await ws2.send("login Bob pass123")
            await ws2.recv()  # logged_in

            await ws1.send("play")
            await ws1.recv()  # searching_for_opponent
            await ws2.send("play")
            await ws2.recv()  # searching_for_opponent

            role1 = await ws1.recv()
            role2 = await ws2.recv()

        self.assertEqual({role1, role2}, {"role: w", "role: b"})

    async def test_lone_player_times_out_when_no_opponent_found(self):
        _, uri = await self._start_server()

        with mock.patch.object(matchmaking, "MATCH_TIMEOUT_SECONDS", 0.2):
            async with websockets.connect(uri) as ws:
                await ws.send("login Alice pass123")
                await ws.recv()  # logged_in
                await ws.send("play")
                await ws.recv()  # searching_for_opponent

                reply = await asyncio.wait_for(ws.recv(), timeout=2)

                with self.assertRaises(websockets.exceptions.ConnectionClosed):
                    await ws.recv()

        self.assertEqual(reply, "error: cannot find opponent")

    async def test_players_far_apart_in_elo_are_not_matched(self):
        server, uri = await self._start_server()
        db.authenticate_or_register(server.db_conn, "Carol", "pass123")
        db.update_elo(server.db_conn, "Carol", 1600)

        with mock.patch.object(matchmaking, "MATCH_TIMEOUT_SECONDS", 0.2):
            async with websockets.connect(uri) as ws1, websockets.connect(uri) as ws2:
                await ws1.send("login Alice pass123")  # elo 1200
                await ws1.recv()  # logged_in
                await ws2.send("login Carol pass123")  # elo 1600
                await ws2.recv()  # logged_in

                await ws1.send("play")
                await ws1.recv()  # searching_for_opponent
                await ws2.send("play")
                await ws2.recv()  # searching_for_opponent

                reply1 = await asyncio.wait_for(ws1.recv(), timeout=2)
                reply2 = await asyncio.wait_for(ws2.recv(), timeout=2)

        self.assertEqual(reply1, "error: cannot find opponent")
        self.assertEqual(reply2, "error: cannot find opponent")


if __name__ == '__main__':
    unittest.main()
