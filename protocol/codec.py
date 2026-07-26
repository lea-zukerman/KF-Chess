"""JSON wire encoding for protocol messages: dataclass instance <-> str.

The only place that knows the on-the-wire JSON shape ({"type": ..., <fields>}).
Works purely on strings/objects -- no websocket dependency, so it's testable
without a running server or client.
"""

from __future__ import annotations

import dataclasses
import json

from . import messages

_MESSAGE_CLASSES = (
    messages.LoginRequest,
    messages.PlayRequest,
    messages.CreateRoomRequest,
    messages.JoinRoomRequest,
    messages.MoveCommand,
    messages.JumpCommand,
    messages.LoggedIn,
    messages.SearchingForOpponent,
    messages.RoomCreated,
    messages.RoleAssigned,
    messages.PlayerJoined,
    messages.StateUpdate,
    messages.ResignCountdown,
    messages.ErrorMessage,
    messages.AuthError,
    messages.MoveRejected,
)

MESSAGE_TYPES: dict[str, type] = {cls.type: cls for cls in _MESSAGE_CLASSES}


class UnknownMessageType(ValueError):
    pass


def encode(message: object) -> str:
    payload = dataclasses.asdict(message)
    payload["type"] = message.type
    return json.dumps(payload)


def decode(raw: str) -> object:
    payload = json.loads(raw)
    message_type = payload.pop("type")
    cls = MESSAGE_TYPES.get(message_type)
    if cls is None:
        raise UnknownMessageType(message_type)
    return cls(**payload)
