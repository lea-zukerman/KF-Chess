"""Command registry: maps an incoming protocol command message to the
GameSession call that services it. Adding a new command means writing one
registered function here -- nothing else in server/ needs to change.

Turn/observer authorization is NOT handled here (that's generic policy that
applies to every command, decided by match.py before dispatch is called);
handlers here only translate one specific command into an engine call.
"""

from __future__ import annotations

from typing import Callable

from kungfu_chess.rules.algebraic import algebraic_to_cell
from protocol.messages import ErrorMessage, JumpCommand, MoveCommand

COMMAND_HANDLERS: dict[type, Callable] = {}


def register(message_type: type):
    def decorator(fn: Callable) -> Callable:
        COMMAND_HANDLERS[message_type] = fn
        return fn
    return decorator


def dispatch(match, role: str, command: object, now_ms: int) -> ErrorMessage | None:
    handler = COMMAND_HANDLERS.get(type(command))
    if handler is None:
        return ErrorMessage(f"unknown command {type(command).__name__}")
    return handler(match, role, command, now_ms)


@register(MoveCommand)
def _handle_move(match, role: str, command: MoveCommand, now_ms: int) -> ErrorMessage | None:
    rows = match.session.engine.board.rows
    try:
        from_row, from_col = algebraic_to_cell(command.from_square, rows)
        to_row, to_col = algebraic_to_cell(command.to_square, rows)
    except ValueError as exc:
        return ErrorMessage(str(exc))

    accepted = match.session.request_move(from_row, from_col, to_row, to_col, now_ms, role)
    if not accepted:
        return ErrorMessage("illegal move")
    return None


@register(JumpCommand)
def _handle_jump(match, role: str, command: JumpCommand, now_ms: int) -> ErrorMessage | None:
    rows = match.session.engine.board.rows
    try:
        row, col = algebraic_to_cell(command.square, rows)
    except ValueError as exc:
        return ErrorMessage(str(exc))

    accepted = match.session.request_jump(row, col, now_ms, role)
    if not accepted:
        return ErrorMessage("illegal move")
    return None
