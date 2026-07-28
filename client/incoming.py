"""Incoming server-message dispatch for the graphical client.

Every server->client message is routed through an @register handler. Because
the connection passes through three phases that need different handler shapes,
there are three small tables:

    LOGIN_HANDLERS  handler(message) -> (ok, reason)        one login reply
    ENTER_HANDLERS  handler(ctx, message) -> result | None  waiting for a game
    GAME_HANDLERS   handler(window, message) -> None        the in-game stream

The in-game stream is the natural dispatch case -- every message just updates
the window. The two handshake tables also route by @register, but their
handlers return a control signal the loop acts on (done / keep waiting) or
raise HandshakeFailed, because a handshake message can mean "done", "still
waiting", or "failed".
"""

from __future__ import annotations

from tkinter import messagebox
from typing import Callable

from protocol.messages import (
    AuthError,
    ErrorMessage,
    LoggedIn,
    MoveRejected,
    ResignCountdown,
    RoleAssigned,
    RoomCreated,
    SearchingForOpponent,
    StateUpdate,
)


class HandshakeFailed(Exception):
    """Login/matchmaking could not reach a live game (bad auth, no opponent,
    unknown room)."""


# ---------------- login phase ----------------

LOGIN_HANDLERS: dict[type, Callable] = {}


def login_handler(message_type: type):
    def decorator(fn: Callable) -> Callable:
        LOGIN_HANDLERS[message_type] = fn
        return fn
    return decorator


def dispatch_login(message: object) -> tuple[bool, str]:
    """Route one login reply. Returns (authenticated, reason)."""
    handler = LOGIN_HANDLERS.get(type(message))
    if handler is None:
        return False, "unexpected response"
    return handler(message)


@login_handler(LoggedIn)
def _login_ok(message: LoggedIn) -> tuple[bool, str]:
    return True, ""


@login_handler(AuthError)
def _login_failed(message: AuthError) -> tuple[bool, str]:
    return False, message.reason


# ---------------- enter-game phase ----------------

class EnterContext:
    """State that accumulates while waiting for a game to start."""

    def __init__(self):
        self.created_room_id: str | None = None


ENTER_HANDLERS: dict[type, Callable] = {}


def enter_handler(message_type: type):
    def decorator(fn: Callable) -> Callable:
        ENTER_HANDLERS[message_type] = fn
        return fn
    return decorator


def dispatch_enter(ctx: EnterContext, message: object) -> tuple[str, str | None] | None:
    """Route one message received while waiting for a game. Returns
    (role, room_id) once the game starts, or None to keep waiting. Raises
    HandshakeFailed on failure."""
    handler = ENTER_HANDLERS.get(type(message))
    if handler is None:
        return None
    return handler(ctx, message)


@enter_handler(RoleAssigned)
def _role_assigned(ctx: EnterContext, message: RoleAssigned) -> tuple[str, str | None]:
    return message.role, ctx.created_room_id


@enter_handler(RoomCreated)
def _room_created(ctx: EnterContext, message: RoomCreated) -> None:
    ctx.created_room_id = message.room_id
    print(f"\n=== ROOM CREATED: {message.room_id} -- share this id. "
          f"Waiting for a player to join... ===\n")
    messagebox.showinfo(
        "Kung Fu Chess",
        f"Room created: {message.room_id}\n\n"
        "Share this id with the other player. Waiting for them to join...",
    )
    return None


@enter_handler(SearchingForOpponent)
def _searching(ctx: EnterContext, message: SearchingForOpponent) -> None:
    print("Searching for an opponent...")
    return None


@enter_handler(ErrorMessage)
def _enter_error(ctx: EnterContext, message: ErrorMessage) -> None:
    raise HandshakeFailed(f"could not start game: {message.message}")


# ---------------- in-game phase ----------------

GAME_HANDLERS: dict[type, Callable] = {}


def game_handler(message_type: type):
    def decorator(fn: Callable) -> Callable:
        GAME_HANDLERS[message_type] = fn
        return fn
    return decorator


def dispatch_game(window, message: object) -> None:
    """Route one in-game message to its handler. A message with no handler is
    ignored -- the server is trusted, so an unhandled type is simply not shown
    rather than an error."""
    handler = GAME_HANDLERS.get(type(message))
    if handler is not None:
        handler(window, message)


@game_handler(StateUpdate)
def _on_state_update(window, message: StateUpdate) -> None:
    window.apply_state(message)


@game_handler(MoveRejected)
def _on_move_rejected(window, message: MoveRejected) -> None:
    window.set_status(f"move rejected: {message.reason}")


@game_handler(ResignCountdown)
def _on_resign_countdown(window, message: ResignCountdown) -> None:
    window.set_status(f"opponent disconnected: {message.seconds_remaining}s")
