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
    CreateRoomRequest,
    JoinRoomRequest,
    LoginRequest,
    PlayRequest,
)
from transport.connection import Connection, ConnectionClosed

from . import incoming
from .game_window import GameWindow
from .incoming import HandshakeFailed

logger = logging.getLogger(__name__)

DEFAULT_PIECES_DIR = r"c:\Users\USER\Desktop\repo\CTD26\pieces2"


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


def _ask_home_choice() -> tuple[str, str | None] | None:
    """Home screen: pick a way into a game. Mirrors the CLI's play/room
    commands as a small "windows message with a text box and buttons".

    Returns ('play', None), ('create', None), ('join', room_id), or None
    if the player cancelled.
    """
    root = tk.Tk()
    root.title("Kung Fu Chess")
    result: list[tuple[str, str | None] | None] = [None]

    def choose(action: str, room_id: str | None = None) -> None:
        result[0] = (action, room_id)
        root.destroy()

    tk.Label(root, text="How do you want to play?").grid(row=0, column=0, columnspan=2, padx=10, pady=8)
    tk.Button(root, text="Play (matchmaking)", width=24,
              command=lambda: choose("play")).grid(row=1, column=0, columnspan=2, padx=10, pady=4)

    tk.Label(root, text="Room id:").grid(row=2, column=0, padx=10, pady=4, sticky="e")
    entry = tk.Entry(root)
    entry.grid(row=2, column=1, padx=10, pady=4)

    def join() -> None:
        room_id = entry.get().strip()
        if room_id:
            choose("join", room_id)

    tk.Button(root, text="Create room", width=11,
              command=lambda: choose("create")).grid(row=3, column=0, padx=6, pady=6)
    tk.Button(root, text="Join room", width=11, command=join).grid(row=3, column=1, padx=6, pady=6)
    tk.Button(root, text="Cancel", width=11, command=root.destroy).grid(row=4, column=0, columnspan=2, pady=6)

    root.mainloop()
    return result[0]


async def _login(host: str, port: int) -> tuple[Connection, str] | None:
    """Prompt for credentials and validate them with the server right away,
    re-prompting on failure. Returns an authenticated (connection, username),
    or None if cancelled.

    A fresh connection is opened for each attempt because the server closes
    the socket on a failed login -- so the same connection can't be retried.
    Kept separate from _enter_game so a wrong password is reported at the
    login step, before the home-screen dialog, not later.
    """
    while True:
        credentials = _ask_login()
        if credentials is None:
            return None
        username, password = credentials
        connection = await Connection.connect(host, port)
        await connection.send(LoginRequest(username, password))
        reply = await connection.receive()
        ok, reason = incoming.dispatch_login(reply)
        if ok:
            return connection, username
        await connection.close()
        messagebox.showerror("Kung Fu Chess", f"Login failed: {reason}")


async def _enter_game(connection: Connection, action: str,
                      room_id: str | None) -> tuple[str, str | None]:
    """Send the chosen home-screen action (play/create/join) and wait until a
    game starts; return the assigned role ('w'/'b'/'observer') and the room id
    the game was created with (None for matchmaking).

    Raises HandshakeFailed on an unknown room or when no opponent is found.
    """
    if action == "play":
        await connection.send(PlayRequest())
    elif action == "create":
        await connection.send(CreateRoomRequest())
    elif action == "join":
        await connection.send(JoinRoomRequest(room_id))
    else:
        raise HandshakeFailed(f"unknown action: {action}")

    ctx = incoming.EnterContext()
    async for message in connection:
        result = incoming.dispatch_enter(ctx, message)
        if result is not None:
            return result
    raise HandshakeFailed("connection closed before a game started")


async def _receive_loop(connection: Connection, window: GameWindow) -> None:
    try:
        async for message in connection:
            incoming.dispatch_game(window, message)
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


async def run(host: str, port: int, pieces_dir: str) -> None:
    login_result = await _login(host, port)
    if login_result is None:
        print("Login cancelled.")
        return
    connection, _username = login_result

    choice = _ask_home_choice()
    if choice is None:
        print("Cancelled.")
        await connection.close()
        return
    action, room_id = choice

    try:
        role, created_room_id = await _enter_game(connection, action, room_id)
    except HandshakeFailed as exc:
        logger.info("%s", exc)
        messagebox.showerror("Kung Fu Chess", str(exc))
        await connection.close()
        return

    display_room = created_room_id if action == "create" else (room_id if action == "join" else None)
    logger.info("joined game as %s (room %s)", role, display_room)
    window = GameWindow(pieces_dir, role, room_id=display_room)
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

    try:
        asyncio.run(run(args.host, args.port, args.pieces_dir))
    except (KeyboardInterrupt, ConnectionClosed):
        pass


if __name__ == "__main__":
    main()
