"""Home-screen command dispatch: the post-login lobby's counterpart to
server/commands.py. Each way a player can enter a game (Play / Create room /
Join room) is a handler registered by message class, so server.py neither
enumerates the message types nor holds any per-flow logic -- it just loops
and calls dispatch().

Handlers receive the GameServer (for its matchmaker/room_manager and the
shared pending-match state), the connection, and the message. They return
True when the connection has been handed off to a Match (the lobby loop
should end) or False to keep the player on the home screen (e.g. an unknown
room id, so they can try another).
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable

from protocol.messages import (
    AttachToMatch,
    CreateRoomRequest,
    ErrorMessage,
    JoinRoomRequest,
    PlayRequest,
    RoomCreated,
    SearchingForOpponent,
)
from transport.connection import Connection
from transport.relay import relay

from server import db
from server.matchmaking import NoOpponentFound
from server.rooms import RoomAbandoned, RoomNotFound

logger = logging.getLogger(__name__)

FLOW_EXPECTED_HOME_COMMAND = "EXPECTED_HOME_COMMAND"
FLOW_NO_OPPONENT_FOUND = "NO_OPPONENT_FOUND"
ROOM_NOT_FOUND = "ROOM_NOT_FOUND"
ROOM_ABANDONED = "ROOM_ABANDONED"

LobbyHandler = Callable[..., Awaitable[bool]]
LOBBY_HANDLERS: dict[type, LobbyHandler] = {}


def register(message_type: type):
    def decorator(fn: LobbyHandler) -> LobbyHandler:
        LOBBY_HANDLERS[message_type] = fn
        return fn
    return decorator


async def dispatch(server, connection, username: str, message: object) -> bool:
    """Route one home-screen message to its handler. Unknown messages get an
    error and keep the player on the home screen (returns False)."""
    handler = LOBBY_HANDLERS.get(type(message))
    if handler is None:
        await connection.send(ErrorMessage(FLOW_EXPECTED_HOME_COMMAND))
        return False
    return await handler(server, connection, username, message)


@register(PlayRequest)
async def _handle_play(server, connection, username: str, message: PlayRequest) -> bool:
    elo_rating = db.get_elo(server.db_conn, username)
    await connection.send(SearchingForOpponent())
    logger.info("client '%s' (elo %d) entered matchmaking", username, elo_rating)

    try:
        opponent_username, _opponent_elo = await server.matchmaker.find_match(username, elo_rating)
    except NoOpponentFound:
        await connection.send(ErrorMessage(FLOW_NO_OPPONENT_FOUND))
        await connection.close()
        return True

    white_username, black_username = sorted((username, opponent_username))
    role = "w" if username == white_username else "b"
    logger.info("client '%s' matched with '%s' as %s", username, opponent_username, role)
    await _relay_to_shard(server, connection, white_username, black_username, role)
    return True


@register(CreateRoomRequest)
async def _handle_create_room(server, connection, username: str, message: CreateRoomRequest) -> bool:
    room_id = await server.room_manager.create_room(username)
    logger.info("client '%s' created room %s", username, room_id)
    await connection.send(RoomCreated(room_id))

    try:
        opponent_username = await server.room_manager.wait_for_opponent(room_id)
    except RoomAbandoned:
        await connection.send(ErrorMessage(ROOM_ABANDONED))
        await connection.close()
        return True

    logger.info("client '%s' matched with '%s' in room %s", username, opponent_username, room_id)
    # The creator is white, per Server_Design.md 5.3. Rooms ignore rating, so
    # unlike the Play flow there is nothing to sort the pair by.
    await _relay_to_shard(server, connection, username, opponent_username, "w")
    return True


@register(JoinRoomRequest)
async def _handle_join_room(server, connection, username: str, message: JoinRoomRequest) -> bool:
    try:
        white, black, role = await server.room_manager.join_room(message.room_id, username)
    except RoomNotFound:
        await connection.send(ErrorMessage(ROOM_NOT_FOUND))
        return False

    logger.info("client '%s' joined room %s as %s", username, message.room_id, role)
    await _relay_to_shard(server, connection, white, black, role)
    return True


async def _relay_to_shard(server, connection, white: str, black: str, role: str) -> None:
    """Hand this player's connection to the shard running their game.

    Both players' gateways name the same (white, black) pair, so the
    allocator gives them the same shard and they meet on one Match without
    talking to each other. The pair they can derive alone; the shard they
    cannot, which is the whole reason the allocator exists. From here the
    gateway only copies messages.
    """
    host, port = await server.locate_shard(white, black)
    upstream = await Connection.connect(host, port)
    await upstream.send(AttachToMatch(white, black, role))
    await relay(connection, upstream)
