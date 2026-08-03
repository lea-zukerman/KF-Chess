"""Structured wire-protocol messages shared by server and client.

Each message is a frozen dataclass tagged with a `type` string used as the
JSON envelope discriminator (see protocol/codec.py). Neither side parses
free-text lines -- both server and client import these classes directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


# ---- client -> server ----

@dataclass(frozen=True)
class LoginRequest:
    type: ClassVar[str] = "login"
    username: str
    password: str


@dataclass(frozen=True)
class PlayRequest:
    type: ClassVar[str] = "play"


@dataclass(frozen=True)
class CreateRoomRequest:
    type: ClassVar[str] = "create_room"


@dataclass(frozen=True)
class JoinRoomRequest:
    type: ClassVar[str] = "join_room"
    room_id: str


@dataclass(frozen=True)
class MoveCommand:
    type: ClassVar[str] = "move"
    from_square: str
    to_square: str


@dataclass(frozen=True)
class JumpCommand:
    type: ClassVar[str] = "jump"
    square: str


# ---- gateway -> shard ----

@dataclass(frozen=True)
class AttachToMatch:
    """Sent once, as the first message on a gateway's connection to a shard.

    The gateway has already decided who plays whom, so the shard is told
    rather than asked. Both players' gateways derive the same (white, black)
    pair independently, which is what lets two separate connections meet on
    one Match without the shard coordinating anything.
    """
    type: ClassVar[str] = "attach_to_match"
    white: str
    black: str
    role: str


# ---- server -> client ----

@dataclass(frozen=True)
class LoggedIn:
    type: ClassVar[str] = "logged_in"


@dataclass(frozen=True)
class SearchingForOpponent:
    type: ClassVar[str] = "searching_for_opponent"


@dataclass(frozen=True)
class RoomCreated:
    type: ClassVar[str] = "room_created"
    room_id: str


@dataclass(frozen=True)
class RoleAssigned:
    type: ClassVar[str] = "role_assigned"
    role: str


@dataclass(frozen=True)
class PlayerJoined:
    type: ClassVar[str] = "player_joined"
    role: str
    username: str


@dataclass(frozen=True)
class StateUpdate:
    type: ClassVar[str] = "state_update"
    board: str
    white_name: str
    black_name: str
    white_elo: int
    black_elo: int
    score_w: int
    score_b: int
    turn: str
    game_over: bool
    winner: str | None = None


@dataclass(frozen=True)
class ResignCountdown:
    type: ClassVar[str] = "resign_countdown"
    seconds_remaining: int


@dataclass(frozen=True)
class ErrorMessage:
    type: ClassVar[str] = "error"
    message: str


@dataclass(frozen=True)
class AuthError:
    type: ClassVar[str] = "auth_error"
    reason: str


@dataclass(frozen=True)
class MoveRejected:
    type: ClassVar[str] = "move_rejected"
    reason: str
