"""Minimal text WebSocket client: proves send-commands/receive-state works
end to end over the structured protocol. Not the real player UI -- see
kungfu_chess/view/game_app.py for that (still local/hotseat; networked
client is a separate follow-up)."""

import argparse
import asyncio
import logging

import websockets

from protocol import codec
from protocol.messages import JumpCommand, LoginRequest, MoveCommand, PlayRequest

logger = logging.getLogger(__name__)


def _parse_input(line: str) -> object | None:
    parts = line.split()
    if not parts:
        return None
    if parts[0] == "play" and len(parts) == 1:
        return PlayRequest()
    if parts[0] == "move" and len(parts) == 3:
        return MoveCommand(parts[1], parts[2])
    if parts[0] == "jump" and len(parts) == 2:
        return JumpCommand(parts[1])
    print(f"unrecognized input: {line!r} (expected: play | move <from> <to> | jump <square>)")
    return None


async def _receive_loop(websocket) -> None:
    async for raw in websocket:
        message = codec.decode(raw)
        logger.info("received: %r", message)
        print(message)


async def _send_loop(websocket) -> None:
    loop = asyncio.get_event_loop()
    while True:
        try:
            line = await loop.run_in_executor(None, input)
        except EOFError:
            return
        message = _parse_input(line)
        if message is None:
            continue
        logger.info("sending: %r", message)
        await websocket.send(codec.encode(message))


async def run_client(host: str = "localhost", port: int = 8765) -> None:
    uri = f"ws://{host}:{port}"
    async with websockets.connect(uri) as websocket:
        username = input("Username: ").strip() or "anonymous"
        password = input("Password: ").strip()
        await websocket.send(codec.encode(LoginRequest(username, password)))
        print(f"Connected to {uri} as {username!r}.")
        receive_task = asyncio.create_task(_receive_loop(websocket))
        send_task = asyncio.create_task(_send_loop(websocket))
        done, pending = await asyncio.wait(
            {receive_task, send_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()


def main() -> None:
    parser = argparse.ArgumentParser(description="Kung Fu Chess CLI WebSocket client")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        asyncio.run(run_client(args.host, args.port))
    except (KeyboardInterrupt, websockets.exceptions.ConnectionClosed):
        pass


if __name__ == "__main__":
    main()
