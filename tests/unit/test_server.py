import asyncio
import unittest
from unittest import mock

import fakeredis.aioredis
import websockets

from protocol import codec
from protocol.messages import (
    AuthError,
    CreateRoomRequest,
    ErrorMessage,
    JoinRoomRequest,
    LoggedIn,
    LoginRequest,
    MoveCommand,
    PlayRequest,
    RoleAssigned,
    RoomCreated,
    SearchingForOpponent,
)
from server import db, matchmaking
from server.lobby import FLOW_EXPECTED_HOME_COMMAND, FLOW_NO_OPPONENT_FOUND, ROOM_NOT_FOUND
from server.server import (
    AUTH_EXPECTED_LOGIN,
    AUTH_INVALID_CREDENTIALS,
    GameServer,
)


class GameServerTests(unittest.IsolatedAsyncioTestCase):
    async def _start_server(self, db_url=":memory:"):
        server = GameServer(db_url=db_url, redis_client=fakeredis.aioredis.FakeRedis())
        ws_server = await websockets.serve(server.handle_client, "localhost", 0)
        self.addAsyncCleanup(ws_server.close)
        port = ws_server.sockets[0].getsockname()[1]
        return server, f"ws://localhost:{port}"

    async def test_login_prompts_for_play(self):
        _, uri = await self._start_server()

        async with websockets.connect(uri) as ws:
            await ws.send(codec.encode(LoginRequest("Alice", "pass123")))
            reply = codec.decode(await ws.recv())

        self.assertEqual(reply, LoggedIn())

    async def test_malformed_login_is_rejected(self):
        _, uri = await self._start_server()

        async with websockets.connect(uri) as ws:
            await ws.send("not valid json")
            reply = codec.decode(await ws.recv())

            with self.assertRaises(websockets.exceptions.ConnectionClosed):
                await ws.recv()

        self.assertEqual(reply, AuthError(AUTH_EXPECTED_LOGIN))

    async def test_wrong_password_is_rejected_and_closes_the_connection(self):
        _, uri = await self._start_server()

        async with websockets.connect(uri) as ws1:
            await ws1.send(codec.encode(LoginRequest("Alice", "pass123")))
            await ws1.recv()

        async with websockets.connect(uri) as ws2:
            await ws2.send(codec.encode(LoginRequest("Alice", "wrongpass")))
            reply = codec.decode(await ws2.recv())

            with self.assertRaises(websockets.exceptions.ConnectionClosed):
                await ws2.recv()

        self.assertEqual(reply, AuthError(AUTH_INVALID_CREDENTIALS))

    async def test_command_before_play_is_rejected_but_connection_stays_open(self):
        _, uri = await self._start_server()

        with mock.patch.object(matchmaking, "MATCH_TIMEOUT_SECONDS", 0.2):
            async with websockets.connect(uri) as ws:
                await ws.send(codec.encode(LoginRequest("Alice", "pass123")))
                await ws.recv()  # logged_in

                await ws.send(codec.encode(MoveCommand("e2", "e4")))
                error_reply = codec.decode(await ws.recv())

                await ws.send(codec.encode(PlayRequest()))
                searching_reply = codec.decode(await ws.recv())
                timeout_reply = codec.decode(await asyncio.wait_for(ws.recv(), timeout=2))

        self.assertEqual(error_reply, ErrorMessage(FLOW_EXPECTED_HOME_COMMAND))
        self.assertEqual(searching_reply, SearchingForOpponent())
        self.assertEqual(timeout_reply, ErrorMessage(FLOW_NO_OPPONENT_FOUND))

    async def test_two_players_within_elo_range_are_matched_and_receive_roles(self):
        _, uri = await self._start_server()

        async with websockets.connect(uri) as ws1, websockets.connect(uri) as ws2:
            await ws1.send(codec.encode(LoginRequest("Alice", "pass123")))
            await ws1.recv()  # logged_in
            await ws2.send(codec.encode(LoginRequest("Bob", "pass123")))
            await ws2.recv()  # logged_in

            await ws1.send(codec.encode(PlayRequest()))
            await ws1.recv()  # searching_for_opponent
            await ws2.send(codec.encode(PlayRequest()))
            await ws2.recv()  # searching_for_opponent

            role1 = codec.decode(await ws1.recv())
            role2 = codec.decode(await ws2.recv())

        self.assertEqual({role1, role2}, {RoleAssigned("w"), RoleAssigned("b")})

    async def test_lone_player_times_out_when_no_opponent_found(self):
        _, uri = await self._start_server()

        with mock.patch.object(matchmaking, "MATCH_TIMEOUT_SECONDS", 0.2):
            async with websockets.connect(uri) as ws:
                await ws.send(codec.encode(LoginRequest("Alice", "pass123")))
                await ws.recv()  # logged_in
                await ws.send(codec.encode(PlayRequest()))
                await ws.recv()  # searching_for_opponent

                reply = codec.decode(await asyncio.wait_for(ws.recv(), timeout=2))

                with self.assertRaises(websockets.exceptions.ConnectionClosed):
                    await ws.recv()

        self.assertEqual(reply, ErrorMessage(FLOW_NO_OPPONENT_FOUND))

    async def test_players_far_apart_in_elo_are_not_matched(self):
        server, uri = await self._start_server()
        db.authenticate_or_register(server.db_conn, "Carol", "pass123")
        db.update_elo(server.db_conn, "Carol", 1600)

        with mock.patch.object(matchmaking, "MATCH_TIMEOUT_SECONDS", 0.2):
            async with websockets.connect(uri) as ws1, websockets.connect(uri) as ws2:
                await ws1.send(codec.encode(LoginRequest("Alice", "pass123")))  # elo 1200
                await ws1.recv()  # logged_in
                await ws2.send(codec.encode(LoginRequest("Carol", "pass123")))  # elo 1600
                await ws2.recv()  # logged_in

                await ws1.send(codec.encode(PlayRequest()))
                await ws1.recv()  # searching_for_opponent
                await ws2.send(codec.encode(PlayRequest()))
                await ws2.recv()  # searching_for_opponent

                reply1 = codec.decode(await asyncio.wait_for(ws1.recv(), timeout=2))
                reply2 = codec.decode(await asyncio.wait_for(ws2.recv(), timeout=2))

        self.assertEqual(reply1, ErrorMessage(FLOW_NO_OPPONENT_FOUND))
        self.assertEqual(reply2, ErrorMessage(FLOW_NO_OPPONENT_FOUND))

    async def test_create_room_returns_id_and_second_joiner_becomes_black(self):
        _, uri = await self._start_server()

        async with websockets.connect(uri) as ws1, websockets.connect(uri) as ws2:
            await ws1.send(codec.encode(LoginRequest("Alice", "pass123")))
            await ws1.recv()  # logged_in
            await ws2.send(codec.encode(LoginRequest("Bob", "pass123")))
            await ws2.recv()  # logged_in

            await ws1.send(codec.encode(CreateRoomRequest()))
            created = codec.decode(await ws1.recv())
            self.assertIsInstance(created, RoomCreated)

            await ws2.send(codec.encode(JoinRoomRequest(created.room_id)))
            role1 = codec.decode(await ws1.recv())
            role2 = codec.decode(await ws2.recv())

        self.assertEqual(role1, RoleAssigned("w"))
        self.assertEqual(role2, RoleAssigned("b"))

    async def test_joining_unknown_room_errors_but_keeps_connection_open(self):
        _, uri = await self._start_server()

        async with websockets.connect(uri) as ws:
            await ws.send(codec.encode(LoginRequest("Alice", "pass123")))
            await ws.recv()  # logged_in

            await ws.send(codec.encode(JoinRoomRequest("ZZZZ")))
            error_reply = codec.decode(await ws.recv())

            # still on the home screen: a valid create now succeeds
            await ws.send(codec.encode(CreateRoomRequest()))
            created = codec.decode(await ws.recv())

        self.assertEqual(error_reply, ErrorMessage(ROOM_NOT_FOUND))
        self.assertIsInstance(created, RoomCreated)


if __name__ == '__main__':
    unittest.main()
