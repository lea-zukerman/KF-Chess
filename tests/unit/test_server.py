import unittest

import websockets

from server.server import GameServer


class GameServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_bus_events_are_queued_for_broadcast(self):
        server = GameServer()

        server.bus.publish("move_logged", {"entry": "wP e2-e4"})
        server.bus.publish("score_changed", {"score": {"w": 1, "b": 0}})
        server.bus.publish("game_over", {})
        server.bus.publish("game_started", {})  # not subscribed -> not queued

        queued = []
        while not server._broadcast_queue.empty():
            queued.append(server._broadcast_queue.get_nowait()[0])

        self.assertEqual(queued, ["move_logged", "score_changed", "game_over"])

    async def _start_server(self):
        server = GameServer()
        ws_server = await websockets.serve(server.handle_client, "localhost", 0)
        self.addAsyncCleanup(ws_server.close)
        port = ws_server.sockets[0].getsockname()[1]
        return server, f"ws://localhost:{port}"

    async def test_first_two_connections_are_white_then_black(self):
        _, uri = await self._start_server()

        async with websockets.connect(uri) as ws1:
            role1 = await ws1.recv()
            async with websockets.connect(uri) as ws2:
                role2 = await ws2.recv()

        self.assertEqual(role1, "role: w")
        self.assertEqual(role2, "role: b")

    async def test_existing_player_is_notified_when_a_second_player_joins(self):
        _, uri = await self._start_server()

        async with websockets.connect(uri) as ws1:
            await ws1.recv()  # role
            await ws1.recv()  # initial state (only white connected so far)

            async with websockets.connect(uri) as ws2:
                await ws2.recv()  # role

                notification = await ws1.recv()

        self.assertEqual(notification, "player_joined: b")

    async def test_third_connection_is_observer_and_cannot_move(self):
        _, uri = await self._start_server()
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
        _, uri = await self._start_server()
        async with websockets.connect(uri) as ws1, websockets.connect(uri) as ws2:
            await ws1.recv()  # role
            await ws1.recv()  # initial state
            await ws2.recv()  # role
            await ws2.recv()  # initial state

            await ws2.send("move e7 e5")
            reply = await ws2.recv()

        self.assertEqual(reply, "error: not your turn")

    async def test_malformed_command_replies_with_error_and_connection_stays_usable(self):
        _, uri = await self._start_server()
        async with websockets.connect(uri) as ws1:
            await ws1.recv()  # role
            await ws1.recv()  # initial state

            await ws1.send("teleport a1 h8")
            error_reply = await ws1.recv()

            await ws1.send("move e2 e4")
            move_reply = await ws1.recv()

        self.assertTrue(error_reply.startswith("error:"))
        self.assertTrue(move_reply.startswith("board:"))


if __name__ == '__main__':
    unittest.main()
