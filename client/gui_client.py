"""Networked graphical client.

Orchestration + login only: it connects through transport.Connection, does the
login/play handshake, then runs three cooperative asyncio loops around a
GameWindow -- receive (server -> window state), sender (window intents ->
server), and render (cv2 draw + input polling). All game logic lives on the
server; all drawing/input lives in GameWindow. This file just wires them.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
import tkinter as tk
from tkinter import messagebox, simpledialog

from protocol.messages import (
    AuthError,
    ErrorMessage,
    LoginRequest,
    MoveRejected,
    PlayRequest,
    ResignCountdown,
    RoleAssigned,
    SearchingForOpponent,
    StateUpdate,
)
from transport.connection import Connection, ConnectionClosed

from .game_window import GameWindow

logger = logging.getLogger(__name__)

DEFAULT_PIECES_DIR = r"c:\Users\USER\Desktop\repo\CTD26\pieces2"


class HandshakeFailed(Exception):
    """Login/matchmaking could not reach a live game (bad auth, no opponent)."""


def _ask_login() -> tuple[str, str] | None:
    """Prompt for username/password via tkinter. Returns None if cancelled."""
    root = tk.Tk()
    root.withdraw()
    try:
        username = simpledialog.askstring("Kung Fu Chess", "Username:", parent=root)
        if not username:
            return None
        password = simpledialog.askstring("Kung Fu Chess", "Password:", parent=root)
        if password is None:
            return None
        return username, password
    finally:
        root.destroy()


async def _handshake(connection: Connection, username: str, password: str) -> str:
    """Log in and enter matchmaking; return the assigned role ('w'/'b').

    Raises HandshakeFailed on bad credentials or when no opponent is found.
    """
    await connection.send(LoginRequest(username, password))
    reply = await connection.receive()
    if isinstance(reply, AuthError):
        raise HandshakeFailed(f"login failed: {reply.reason}")

    await connection.send(PlayRequest())
    async for message in connection:
        if isinstance(message, RoleAssigned):
            return message.role
        if isinstance(message, SearchingForOpponent):
            print("Searching for an opponent...")
        elif isinstance(message, ErrorMessage):
            raise HandshakeFailed(f"matchmaking failed: {message.message}")
    raise HandshakeFailed("connection closed before a game started")


async def _receive_loop(connection: Connection, window: GameWindow) -> None:
    try:
        async for message in connection:
            if isinstance(message, StateUpdate):
                window.apply_state(message)
            elif isinstance(message, MoveRejected):
                window.set_status(f"move rejected: {message.reason}")
            elif isinstance(message, ResignCountdown):
                window.set_status(f"opponent disconnected: {message.seconds_remaining}s")
    except ConnectionClosed:
        pass
    finally:
        window.running = False


async def _sender_loop(connection: Connection, window: GameWindow) -> None:
    try:
        while window.running:
            command = await window.outgoing.get()
            await connection.send(command)
    except ConnectionClosed:
        window.running = False


async def _render_loop(window: GameWindow) -> None:
    last = time.monotonic()
    while window.running:
        now = time.monotonic()
        delta_ms = int((now - last) * 1000)
        last = now
        frame = window.render(delta_ms=delta_ms, now_ms=int(now * 1000))
        if window.show(frame) == ord("q"):
            window.running = False
        await asyncio.sleep(0.016)


async def run(host: str, port: int, username: str, password: str, pieces_dir: str) -> None:
    connection = await Connection.connect(host, port)
    try:
        role = await _handshake(connection, username, password)
    except HandshakeFailed as exc:
        logger.info("%s", exc)
        messagebox.showerror("Kung Fu Chess", str(exc))
        await connection.close()
        return

    logger.info("joined game as %s", role)
    window = GameWindow(pieces_dir, role)
    window.open()

    receive_task = asyncio.create_task(_receive_loop(connection, window))
    sender_task = asyncio.create_task(_sender_loop(connection, window))
    try:
        await _render_loop(window)
    finally:
        window.running = False
        receive_task.cancel()
        sender_task.cancel()
        window.close()
        await connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Kung Fu Chess graphical client")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--pieces-dir", default=DEFAULT_PIECES_DIR)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    credentials = _ask_login()
    if credentials is None:
        print("Login cancelled.")
        return
    username, password = credentials

    try:
        asyncio.run(run(args.host, args.port, username, password, args.pieces_dir))
    except (KeyboardInterrupt, ConnectionClosed):
        pass


if __name__ == "__main__":
    main()
