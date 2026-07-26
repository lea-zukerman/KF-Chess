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
server/            WebSocket server:
                   connection.py  - the only file that touches `websockets`
                   server.py      - lobby: login, then the home-screen loop
                   lobby.py       - home-screen command dispatch (play / room)
                   matchmaking.py - ELO-range pairing for "Play"
                   rooms.py       - create/join a game by a shared room id
                   match.py       - one live game: bus, tick loop, broadcast
                   commands.py    - in-match command dispatch (move / jump)
                   db.py, elo.py  - SQLite users/passwords/ratings
client/            cli_client.py  - minimal text client (not the real UI)
```

## Requirements

- Python 3.12+
- [`websockets`](https://pypi.org/project/websockets/) (server and client)
- OpenCV (`cv2`) is optional — only the graphical client uses it, and it
  falls back to `mock_cv2` when it is not installed.

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

## Running the text board parser

```bash
python main.py < input.txt
```

## Running the tests

```bash
python run_tests.py
```
