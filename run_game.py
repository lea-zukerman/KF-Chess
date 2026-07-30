"""One-shot local launcher: starts the server and a few GUI clients so a whole
game can be played without opening several terminals by hand.

    python run_game.py                      # server + 2 player windows
    python run_game.py --players 3
    python run_game.py --no-server          # clients only, server already up

Use --no-server when the server is running under docker compose: it already
holds the port, so starting a second one here just fails to bind. Pass
--host 127.0.0.1 with it -- "localhost" can resolve to ::1 first, which the
container's published port does not answer on.

Each client still shows its own login dialog -- log in with a different
username in each window so matchmaking pairs them. Closing the player windows
(or Ctrl+C) shuts the server down too.
"""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time

from client.gui_client import DEFAULT_PIECES_DIR


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
        server = subprocess.Popen([sys.executable, "-m", "server", "--host", args.host,
                                   "--port", str(args.port)])
        procs.append(server)
        print(f"Started server (pid {server.pid}) on {args.host}:{args.port}")

        if not _wait_until_listening(args.host, args.port):
            print("Server did not start listening in time; shutting down.")
            server.terminate()
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
        for proc in procs:
            if proc.poll() is None:
                proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("All processes stopped.")


if __name__ == "__main__":
    main()
