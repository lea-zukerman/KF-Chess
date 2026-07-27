import asyncio
import unittest
from unittest import mock

import websockets

from protocol import codec
from protocol.messages import ErrorMessage, MoveCommand, MoveRejected, PlayerJoined, ResignCountdown, RoleAssigned, StateUpdate
from server import db
from server import match as match_module
from transport.connection import Connection
from server.match import MOVE_ERROR_OBSERVER, MOVE_ERROR_WRONG_TURN, Match


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
            await self.match.join(Connection(websocket), role)

        ws_server = await websockets.serve(handler, "localhost", 0)
        self.addAsyncCleanup(ws_server.close)
        port = ws_server.sockets[0].getsockname()[1]
        return f"ws://localhost:{port}"

    async def test_white_and_black_get_their_roles_in_connection_order(self):
        uri = await self._start_match()

        async with websockets.connect(uri) as ws1:
            role1 = codec.decode(await ws1.recv())
            async with websockets.connect(uri) as ws2:
                role2 = codec.decode(await ws2.recv())

        self.assertEqual(role1, RoleAssigned("w"))
        self.assertEqual(role2, RoleAssigned("b"))

    async def test_existing_player_is_notified_when_the_other_joins(self):
        uri = await self._start_match()

        async with websockets.connect(uri) as ws1:
            await ws1.recv()  # role
            await ws1.recv()  # initial state (white only)

            async with websockets.connect(uri) as ws2:
                await ws2.recv()  # role

                notification = codec.decode(await ws1.recv())

        self.assertEqual(notification, PlayerJoined("b", "Bob"))

    async def test_third_connection_is_observer_and_cannot_move(self):
        uri = await self._start_match()

        async with websockets.connect(uri) as ws1, \
                websockets.connect(uri) as ws2, \
                websockets.connect(uri) as ws3:
            await ws1.recv()  # role
            await ws2.recv()  # role
            self.assertEqual(codec.decode(await ws3.recv()), RoleAssigned("observer"))
            await ws3.recv()  # initial state broadcast

            await ws3.send(codec.encode(MoveCommand("e2", "e4")))
            reply = codec.decode(await ws3.recv())

        self.assertEqual(reply, MoveRejected(MOVE_ERROR_OBSERVER))

    async def test_black_cannot_move_before_white(self):
        uri = await self._start_match()

        async with websockets.connect(uri) as ws1, websockets.connect(uri) as ws2:
            await ws1.recv()  # role
            await ws1.recv()  # initial state
            await ws2.recv()  # role
            await ws2.recv()  # initial state

            await ws2.send(codec.encode(MoveCommand("e7", "e5")))
            reply = codec.decode(await ws2.recv())

        self.assertEqual(reply, MoveRejected(MOVE_ERROR_WRONG_TURN))

    async def test_malformed_command_replies_with_error_and_connection_stays_usable(self):
        uri = await self._start_match()

        async with websockets.connect(uri) as ws1:
            await ws1.recv()  # role
            await ws1.recv()  # initial state

            await ws1.send("not valid json")
            error_reply = codec.decode(await ws1.recv())

            await ws1.send(codec.encode(MoveCommand("e2", "e4")))
            move_reply = codec.decode(await ws1.recv())

        self.assertIsInstance(error_reply, ErrorMessage)
        self.assertIsInstance(move_reply, StateUpdate)

    async def test_elo_changes_after_a_game_ends(self):
        uri = await self._start_match(board_text="bK .\nwR .")

        async with websockets.connect(uri) as ws1, websockets.connect(uri) as ws2:
            await ws1.recv()  # role
            await ws1.recv()  # initial state (white only)

            await ws2.recv()  # role
            await ws2.recv()  # broadcast after black joined
            await ws1.recv()  # player_joined notification
            await ws1.recv()  # broadcast after black joined

            await ws1.send(codec.encode(MoveCommand("a1", "a2")))
            await ws1.recv()  # move accepted, piece still traveling

            final_state = None
            for _ in range(10):
                message = codec.decode(await asyncio.wait_for(ws1.recv(), timeout=2))
                if isinstance(message, StateUpdate) and message.game_over \
                        and (message.white_elo, message.black_elo) != (1200, 1200):
                    final_state = message
                    break

        self.assertIsNotNone(final_state)

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

                countdown_2 = codec.decode(await asyncio.wait_for(ws2.recv(), timeout=2))
                countdown_1 = codec.decode(await asyncio.wait_for(ws2.recv(), timeout=2))
                final_state = codec.decode(await asyncio.wait_for(ws2.recv(), timeout=2))

        self.assertEqual(countdown_2, ResignCountdown(2))
        self.assertEqual(countdown_1, ResignCountdown(1))
        self.assertIsInstance(final_state, StateUpdate)
        self.assertTrue(final_state.game_over)
        self.assertEqual((final_state.white_elo, final_state.black_elo), (1184, 1216))
        self.assertEqual(db.get_elo(self.db_conn, "Alice"), 1184)
        self.assertEqual(db.get_elo(self.db_conn, "Bob"), 1216)


if __name__ == '__main__':
    unittest.main()
