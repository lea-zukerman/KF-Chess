"""One-shot local launcher: starts the whole server side and a few GUI clients
so a game can be played without opening several terminals by hand.

    python run_game.py                      # 4 services + 2 player windows
    python run_game.py --players 3
    python run_game.py --no-server          # clients only, servers already up

"The server" is now four processes -- two shards, an allocator and a gateway
-- so this brings up the same shape docker-compose.yml does, without Docker.
Redis has to be reachable either way; Play and Room both go through it.

Use --no-server when the stack is running under docker compose: it already
holds the port, so starting a second one here just fails to bind. Pass
--host 127.0.0.1 with it -- "localhost" can resolve to ::1 first, which the
container's published port does not answer on.

Each client still shows its own login dialog -- log in with a different
username in each window so matchmaking pairs them. Closing the player windows
(or Ctrl+C) shuts the server down too.
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time

from client.gui_client import DEFAULT_PIECES_DIR

# The gateway's port is --port; these are the ones behind it. Two shards
# rather than one so the placement decision has something to decide, which
# is the same reason docker-compose.yml runs two.
ALLOCATOR_PORT = 8767
SHARD_PORTS = (8766, 8768)


def _wait_until_listening(host: str, port: int, timeout: float = 10.0) -> bool:
    """Poll host:port until something accepts a TCP connection, or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


class StartupFailed(Exception):
    """A service never started listening, so there is no point going on."""


def _terminate(procs: list[subprocess.Popen]) -> None:
    """Stop everything still running, politely and then not."""
    for proc in procs:
        if proc.poll() is None:
            proc.terminate()
    for proc in procs:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    print("All processes stopped.")


def _start(argv: list[str], name: str, host: str, port: int, env=None) -> subprocess.Popen:
    """Launch one service and wait for its port before returning.

    Waiting matters more than it did with a single process: a gateway that
    comes up before the allocator answers its first placement with a failed
    connect rather than with a retry.
    """
    proc = subprocess.Popen([sys.executable, *argv], env=env)
    print(f"Started {name} (pid {proc.pid}) on {host}:{port}")
    if not _wait_until_listening(host, port):
        proc.terminate()
        raise StartupFailed(f"{name} did not start listening on {host}:{port}")
    return proc


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch the server and player clients")
    parser.add_argument("--players", type=int, default=2, help="number of GUI clients to open")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--pieces-dir", default=DEFAULT_PIECES_DIR)
    parser.add_argument("--no-server", action="store_true",
                        help="attach to a server that is already running")
    args = parser.parse_args()

    procs: list[subprocess.Popen] = []

    if args.no_server:
        if not _wait_until_listening(args.host, args.port, timeout=2.0):
            print(f"Nothing is listening on {args.host}:{args.port}. "
                  f"Start it (docker compose up -d) or drop --no-server.")
            return
        print(f"Using the server already on {args.host}:{args.port}")
    else:
        # Started innermost first: the gateway needs the allocator to answer,
        # and the allocator needs shards to hand out. If any of them fails to
        # come up, the ones already started have to go -- with a single
        # process there was nothing to leave behind.
        try:
            for port in SHARD_PORTS:
                procs.append(_start(["-m", "services.shard", "--host", args.host,
                                     "--port", str(port)], "shard", args.host, port))

            allocator_env = dict(os.environ)
            allocator_env["SHARDS"] = ",".join(f"{args.host}:{port}" for port in SHARD_PORTS)
            procs.append(_start(["-m", "services.allocator", "--host", args.host,
                                 "--port", str(ALLOCATOR_PORT)], "allocator",
                                args.host, ALLOCATOR_PORT, env=allocator_env))

            gateway_env = dict(os.environ)
            gateway_env["ALLOCATOR_HOST"] = args.host
            gateway_env["ALLOCATOR_PORT"] = str(ALLOCATOR_PORT)
            procs.append(_start(["-m", "services.gateway", "--host", args.host,
                                 "--port", str(args.port)], "gateway",
                                args.host, args.port, env=gateway_env))
        except StartupFailed as exc:
            print(f"{exc}; shutting down.")
            _terminate(procs)
            return

    clients: list[subprocess.Popen] = []
    for i in range(args.players):
        client = subprocess.Popen([sys.executable, "-m", "client.gui_client",
                                   "--host", args.host, "--port", str(args.port),
                                   "--pieces-dir", args.pieces_dir])
        clients.append(client)
        procs.append(client)
        print(f"Started player window {i + 1} (pid {client.pid})")

    print("\nLog in with a different username in each window. Close the windows "
          "(or press Ctrl+C here) to stop everything.")

    try:
        # The game is over for us once every player window has closed.
        for client in clients:
            client.wait()
    except KeyboardInterrupt:
        print("\nInterrupted; stopping.")
    finally:
        _terminate(procs)


if __name__ == "__main__":
    main()
