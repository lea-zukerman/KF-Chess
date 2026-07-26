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
    CreateRoomRequest,
    ErrorMessage,
    JoinRoomRequest,
    PlayRequest,
    RoomCreated,
    SearchingForOpponent,
)

from . import db
from .match import Match
from .matchmaking import NoOpponentFound
from .rooms import RoomNotFound

logger = logging.getLogger(__name__)

FLOW_EXPECTED_HOME_COMMAND = "EXPECTED_HOME_COMMAND"
FLOW_NO_OPPONENT_FOUND = "NO_OPPONENT_FOUND"
ROOM_NOT_FOUND = "ROOM_NOT_FOUND"

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
    match = await _get_or_create_match(server, white_username, black_username)
    role = "w" if username == white_username else "b"
    logger.info("client '%s' matched with '%s' as %s", username, opponent_username, role)
    await match.join(connection, role)
    return True


@register(CreateRoomRequest)
async def _handle_create_room(server, connection, username: str, message: CreateRoomRequest) -> bool:
    room_id = await server.room_manager.create_room(username)
    logger.info("client '%s' created room %s", username, room_id)
    await connection.send(RoomCreated(room_id))
    match = await server.room_manager.wait_for_match(room_id)
    await match.join(connection, "w")
    return True


@register(JoinRoomRequest)
async def _handle_join_room(server, connection, username: str, message: JoinRoomRequest) -> bool:
    try:
        match, role = await server.room_manager.join_room(message.room_id, username)
    except RoomNotFound:
        await connection.send(ErrorMessage(ROOM_NOT_FOUND))
        return False
    logger.info("client '%s' joined room %s as %s", username, message.room_id, role)
    await match.join(connection, role)
    return True


async def _get_or_create_match(server, white_username: str, black_username: str) -> Match:
    """Both matched players independently compute the same (white, black) key
    and arrive here separately -- the first to arrive creates the Match, the
    second finds it waiting and consumes the pending entry. The dict/lock live
    on the GameServer (shared per-server state); only this coordination logic
    lives here."""
    key = (white_username, black_username)
    async with server._match_lock:
        match = server._pending_matches.get(key)
        if match is None:
            match = Match(white_username, black_username, server.db_conn)
            match.start()
            server._pending_matches[key] = match
        else:
            del server._pending_matches[key]
    return match
