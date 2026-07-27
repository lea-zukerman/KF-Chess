"""Shared websocket wrapper: the only place in the project that imports
`websockets`. Both the server and the client send/receive protocol message
objects through this, never raw text or JSON. It lives in its own top-level
package (not inside `kungfu_chess/`, which must stay network-free, and not
inside `server/` or `client/`, which must not import each other).
"""

from __future__ import annotations

import websockets

from protocol import codec


class ConnectionClosed(Exception):
    pass


class MalformedMessage:
    """Returned by receive() when the raw payload couldn't be decoded into
    a known protocol message. A value, not a raised exception, so a single
    bad message doesn't break the caller's receive loop -- it flows through
    like any other unexpected message type and gets handled like one."""

    def __init__(self, reason: str):
        self.reason = reason

    def __repr__(self) -> str:
        return f"MalformedMessage({self.reason!r})"


class Connection:
    def __init__(self, websocket):
        self._websocket = websocket

    @classmethod
    async def connect(cls, host: str, port: int) -> "Connection":
        """Client-side helper: open a websocket to host:port and wrap it.
        The server side wraps sockets handed to it by `websockets.serve`."""
        websocket = await websockets.connect(f"ws://{host}:{port}")
        return cls(websocket)

    async def send(self, message: object) -> None:
        try:
            await self._websocket.send(codec.encode(message))
        except websockets.exceptions.ConnectionClosed as exc:
            raise ConnectionClosed from exc

    async def receive(self) -> object:
        try:
            raw = await self._websocket.recv()
        except websockets.exceptions.ConnectionClosed as exc:
            raise ConnectionClosed from exc
        try:
            return codec.decode(raw)
        except (ValueError, TypeError) as exc:
            return MalformedMessage(str(exc))

    async def close(self) -> None:
        await self._websocket.close()

    def __aiter__(self) -> "Connection":
        return self

    async def __anext__(self) -> object:
        try:
            return await self.receive()
        except ConnectionClosed:
            raise StopAsyncIteration
