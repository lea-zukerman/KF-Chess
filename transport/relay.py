"""Bidirectional forwarding between two connections.

This is what makes a gateway a gateway: a player's socket ends there, a second
socket carries the same messages on to the shard running their game, and the
gateway copies between them without interpreting anything. Game rules stay in
the shard's GameEngine, which is the point of Server_Design.md section 5.4 --
neither the client nor the gateway decides them.

Messages are relayed as protocol objects rather than raw text, which costs a
decode and re-encode per hop. At the message rates in section 2.1 that is
worth revisiting; it is kept for now because it means nothing untyped can
cross a gateway.
"""

from __future__ import annotations

import asyncio
import logging

from .connection import Connection, ConnectionClosed, MalformedMessage

logger = logging.getLogger(__name__)


async def _pump(source: Connection, destination: Connection) -> None:
    """Copy messages one way until the source closes."""
    try:
        async for message in source:
            if isinstance(message, MalformedMessage):
                # Not forwardable -- it has no type to encode. Dropping it
                # keeps the relay alive, as receive() intended.
                logger.warning("dropping unrelayable message: %r", message)
                continue
            await destination.send(message)
    except ConnectionClosed:
        pass


async def relay(client: Connection, upstream: Connection) -> None:
    """Forward both ways until either side goes away, then stop the other."""
    tasks = [
        asyncio.create_task(_pump(client, upstream)),
        asyncio.create_task(_pump(upstream, client)),
    ]
    try:
        _done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
    finally:
        # Closing upstream lets the shard see the player leave, which is what
        # starts its disconnect countdown.
        await upstream.close()
