# Kung Fu Chess

A real-time chess variant (pieces travel between cells and have cooldowns
instead of taking strict turns), built as a local game engine with a
networked server layered on top for two-player matches.

The server is not one process. It is split by role — a gateway that holds
player connections, an allocator that decides where a game runs, and shards
that run the games — so that games can spread across machines. See
[Server_Design.md](Server_Design.md) for the reasoning; this file covers
what exists and how to run it.

## Architecture

Dependencies point one way only — game logic never knows about the network,
and the shared core never knows which process it is running in:

```
kungfu_chess/      Pure game logic (model, rules, realtime, engine, app).
                   Knows nothing about sockets, players, or rooms.
protocol/          Wire messages shared by every component:
                   messages.py (one dataclass per message) + codec.py (JSON).
transport/         connection.py - the only file that touches `websockets`
                   relay.py      - copies messages between two connections
server/            Shared core. Used by the services below, imports none of
                   them:
                   match.py       - one live game: bus, tick loop, broadcast
                   commands.py    - in-match command dispatch (move / jump)
                   matchmaking.py - ELO-range pairing for "Play"
                   rooms.py       - create/join a game by a shared room id
                   db.py, elo.py  - users, passwords, ratings
services/          One package per deployed role, each with a __main__:
                   gateway/       - player connections, login, then relay
                   allocator/     - picks the shard for a pair
                   shard/         - runs the games
client/            cli_client.py  - minimal text client
                   gui_client.py  - graphical client (renders server state,
                                    reuses kungfu_chess/view for drawing)
                   game_window.py - the cv2 window + click-to-command input
run_game.py        One-shot local launcher: all services + N player windows.
```

## How the pieces fit

| Role | Responsibility | State |
|------|----------------|-------|
| **Gateway** | Holds the player's socket, authenticates, pairs them, then copies messages to a shard. Runs no game logic. | none of its own |
| **Allocator** | Decides *which shard* a given pair's game runs on. | placements in Redis |
| **Shard** | Runs the games. Its `GameEngine` is the only authority on the rules. | live games, in memory |
| **PostgreSQL** | Users, passwords, ELO. | durable |
| **Redis** | Matchmaking queue, open rooms, placements. | short-lived by nature |

The division that matters: **the matchmaker decides *who* plays whom, the
allocator decides *where* it runs, and the gateway decides neither.** Two
players reach the same game because both their gateways ask the allocator
about the same pair and get the same answer back — the pair they can work
out alone by sorting the two usernames, the shard they cannot. Separating
the two is what lets the fleet grow without limiting who can play whom.

Once a game starts, the gateway is a pipe. Moves travel
`client → gateway → shard`, the shard runs the rules and broadcasts the
result, and nothing in between interprets anything.

## Requirements

- Python 3.12+
- **Docker** for the full deployment (brings up PostgreSQL and Redis itself)
- Server: `websockets`, `redis`, `psycopg[binary]` — see
  `requirements-server.txt`
- Graphical client: OpenCV (`cv2`) and Tk (`tkinter`, bundled with most
  Python installs). The text client needs neither.
- Tests: `fakeredis` (in `requirements.txt`, deliberately not in the server
  image)
- Piece image assets live outside this repo — pass their folder with
  `--pieces-dir` (default points at a local `pieces2` folder).

Redis is required for **Play** and **Room** whichever way you run things:
both the matchmaking queue and the room registry live there.

## Running it

### With Docker (the real deployment)

```bash
docker compose up --build -d
docker compose ps            # postgres, redis, gateway, allocator, shard-1, shard-2
```

Six containers. Only the gateway publishes a port (`8765`); shards and the
allocator are reachable inside the network only, because nothing outside
should talk to them.

Then attach player windows to it:

```bash
python run_game.py --no-server --host 127.0.0.1
```

Pass `--host 127.0.0.1` rather than `localhost` — the latter can resolve to
`::1` first, which the container's published port does not answer on.

Watch the split actually happen, with two pairs playing at once:

```bash
docker compose logs shard-1 shard-2 | grep started
```

On a network that intercepts TLS, build with:

```bash
docker build --build-arg PIP_TRUSTED_HOST="pypi.org files.pythonhosted.org" .
```

### Without Docker

`run_game.py` starts the same four services locally — two shards, an
allocator and a gateway — plus the player windows:

```bash
python run_game.py                 # or: python run_game.py --players 3
```

Log in with a different username in each window; matchmaking pairs them.
Closing the windows (or Ctrl+C) stops everything. A Redis reachable at
`localhost:6379` is still needed; without Docker, run one yourself.

### By hand

Each service is its own entry point. Start them innermost first — the
gateway needs the allocator, and the allocator needs shards:

```bash
python -m services.shard     --port 8766
python -m services.shard     --port 8768
SHARDS=localhost:8766,localhost:8768 python -m services.allocator --port 8767
ALLOCATOR_HOST=localhost ALLOCATOR_PORT=8767 python -m services.gateway --port 8765
```

| Variable | Read by | Meaning |
|----------|---------|---------|
| `DB_URL` | gateway, shard | `postgresql://…`, or any path for SQLite |
| `REDIS_URL` | gateway, allocator | defaults to `redis://localhost:6379` |
| `SHARDS` | allocator | `host:port,host:port` — the fleet |
| `ALLOCATOR_HOST` / `ALLOCATOR_PORT` | gateway | where to ask for a placement |

`DB_URL` takes SQLite as well as PostgreSQL, which is what lets the test
suite run without a database process.

## Playing

Start a text client (one per player):

```bash
python -m client                 # or: python -m client --host <host> --port <port>
```

It prompts for a username and password. The account is created on first
login and reused afterwards (rating starts at 1200 and moves by ELO).

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

## Known limitations

These are deliberate stopping points, not oversights. Each is the next
stage's work — section 12 of [Server_Design.md](Server_Design.md).

- **Run one gateway, not several.** `Matchmaker._wake` only reaches a
  player waiting in its own process. With two gateways, a player waiting on
  one can be claimed out of the Redis queue by a player arriving at the
  other and never be told: they wait out the timeout and hear that no
  opponent was found, while their opponent sits on a shard waiting for a
  connection that never comes. Both halves look like ordinary outcomes,
  which is what makes it worth stating. Shards scale freely; gateways do
  not. The fix belongs on the event bus (§5.2.1).
- **A shard that dies takes its games with it.** Nothing detects it, and a
  stale placement surfaces as a failed connect. §10.3 chose this over
  replicating game state — it protects at most 90 seconds of play.
- **Placement is a direct call, not an event.** §5.2 puts the assignment on
  the event bus so it can be retried; today the gateway asks the allocator
  over a WebSocket and Redis makes the answer idempotent per pair. Enough
  to be correct, not enough to survive a dropped message.
- **The allocator does not measure load.** It round-robins. Weighing shards
  needs them reporting, which is the same event bus.
- **ELO is written on the hot path.** A separate results writer with a
  durable queue (§5.5) is stage 4.

## Running the text board parser

```bash
python main.py < input.txt
```

## Running the tests

```bash
python run_tests.py
```

170 tests, no Docker and no database process needed — `DB_URL` falls back to
SQLite and `fakeredis` stands in for Redis.

One caveat worth knowing before adding tests: **`fakeredis` never yields the
event loop**, so two coroutines cannot interleave between Redis calls in
front of it, and a check-then-act race cannot appear in the suite at all.
`tests/unit/test_matchmaking.py` has a `YieldingRedis` wrapper that adds
back that one property; use it for anything concurrent, and confirm such a
test fails against the unfixed code before trusting it.
