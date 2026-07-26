"""Thin wrapper around one websocket: the only file in server/ that imports
`websockets` directly. Everything above this layer sends/receives protocol
message objects and never touches a raw websocket or JSON string.
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
    like any other unexpected message type and gets an ErrorMessage reply."""

    def __init__(self, reason: str):
        self.reason = reason

    def __repr__(self) -> str:
        return f"MalformedMessage({self.reason!r})"


class Connection:
    def __init__(self, websocket):
        self._websocket = websocket

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
