# Kung Fu Chess

A real-time chess variant (pieces travel between cells and have cooldowns
instead of taking strict turns), built as a local game engine with a
WebSocket server layered on top for networked two-player matches.

## Architecture

Dependencies point one way only — game logic never knows about the network:

```
kungfu_chess/      Pure game logic (model, rules, realtime, engine, app).
                   Knows nothing about sockets, players, or rooms.
protocol/          Wire messages shared by client and server:
                   messages.py (one dataclass per message) + codec.py (JSON).
transport/         connection.py - the only file that touches `websockets`,
                   shared by both server and client (protocol objects in/out).
server/            WebSocket server:
                   server.py      - lobby: login, then the home-screen loop
                   lobby.py       - home-screen command dispatch (play / room)
                   matchmaking.py - ELO-range pairing for "Play"
                   rooms.py       - create/join a game by a shared room id
                   match.py       - one live game: bus, tick loop, broadcast
                   commands.py    - in-match command dispatch (move / jump)
                   db.py, elo.py  - SQLite users/passwords/ratings
client/            cli_client.py  - minimal text client
                   gui_client.py  - graphical client (renders server state,
                                    reuses kungfu_chess/view for drawing)
                   game_window.py - the cv2 window + click-to-command input
run_game.py        One-shot local launcher: server + N player windows.
```

## Requirements

- Python 3.12+
- [`websockets`](https://pypi.org/project/websockets/) (server and client)
- The graphical client also needs OpenCV (`cv2`) and Tk (`tkinter`, bundled
  with most Python installs). The text client needs neither. Piece image
  assets live outside this repo — pass their folder with `--pieces-dir`
  (default points at a local `pieces2` folder).

## Quick start (local, one command)

Launch the server and two player windows together:

```bash
python run_game.py                 # or: python run_game.py --players 3
```

Log in with a different username in each window; matchmaking pairs them.
Closing the windows (or Ctrl+C) stops the server too. To run the pieces
across machines, or with the text client, use the steps below instead.

## Running the networked game

Start the server (defaults to `localhost:8765`):

```bash
python -m server                 # or: python -m server --host 0.0.0.0 --port 8765
```

Then start a client in another terminal (one per player):

```bash
python -m client                 # or: python -m client --host <host> --port <port>
```

The client prompts for a username and password. The account is created on
first login and reused afterwards (rating starts at 1200 and moves by ELO).

Once logged in, type one of the home-screen commands:

| Command             | What it does                                                    |
|---------------------|-----------------------------------------------------------------|
| `play`              | Find an opponent within ±100 ELO (waits up to 1 min).           |
| `room create`       | Open a new room; the printed room id is yours to share.         |
| `room join <id>`    | Join a room by id. The second player is Black; later ones watch.|

**Play** pairs you with a stranger of similar rating. **Room** pairs you
with someone you invite by sharing the room id (no rating filter). Either
way, once two players are in, use the in-game commands:

| Command              | What it does                          |
|----------------------|---------------------------------------|
| `move <from> <to>`   | e.g. `move e2 e4`                     |
| `jump <square>`      | e.g. `jump e4`                        |

Both players (and any observers) receive the same broadcast game state.
If a player disconnects, the game auto-resigns after a 20-second countdown.

### Graphical client

Instead of the text client, run the graphical one (currently "Play" only):

```bash
python -m client.gui_client       # --host / --port / --pieces-dir as above
```

It shows a tkinter login dialog, then opens a board window. Left-click a
source cell then a destination to move; right-click a piece to jump it in
place; press `q` to quit. `run_game.py` launches this client for you.

## Running the text board parser

```bash
python main.py < input.txt
```

## Running the tests

```bash
python run_tests.py
```
