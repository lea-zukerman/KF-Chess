"""ELO-range pairing for the "Play" flow.

The pool of waiting players lives in Redis, in two sorted sets over the same
members: one scored by rating, which is what makes "find someone within
+-100" a range query instead of a scan, and one scored by the time they
joined, which is what lets any process drop players who have waited too
long. See Server_Design.md section 5.2.1.

Waiting itself is still an asyncio.Event in this process. That is the half
this stage does not move: a player is woken by the process holding their
connection, and until there is a message bus to wake them across processes,
moving it out would mean writing something untestable.
"""

import asyncio
import time

from redis.exceptions import WatchError

ELO_RANGE = 100
MATCH_TIMEOUT_SECONDS = 60

# Same members in both, scored differently: one to search by, one to expire by.
WAITING_BY_ELO = "waiting:elo"
WAITING_BY_TIME = "waiting:time"


class NoOpponentFound(Exception):
    pass


class _WaitingPlayer:
    def __init__(self, elo: int):
        self.elo = elo
        self.opponent: tuple[str, int] | None = None
        self.event = asyncio.Event()


class Matchmaker:
    def __init__(self, redis):
        self.redis = redis
        self._waiting: dict[str, _WaitingPlayer] = {}

    async def find_match(self, username: str, elo: int) -> tuple[str, int]:
        """Pair with a waiting player within ELO_RANGE, or join the pool and
        wait to be picked. Raises NoOpponentFound after MATCH_TIMEOUT_SECONDS."""
        await self._drop_expired()

        # Registered before the pool can contain me, so there is no instant
        # where another player can claim me out of Redis and find nobody to
        # wake.
        me = _WaitingPlayer(elo)
        self._waiting[username] = me
        try:
            opponent = await self._claim_or_enqueue(username, elo)
            if opponent is not None:
                self._wake(opponent[0], username, elo)
                return opponent

            await asyncio.wait_for(me.event.wait(), timeout=MATCH_TIMEOUT_SECONDS)
            return me.opponent
        except asyncio.TimeoutError:
            raise NoOpponentFound(username)
        finally:
            self._waiting.pop(username, None)
            await self._dequeue(username)

    async def _claim_or_enqueue(self, username: str, elo: int) -> tuple[str, int] | None:
        """Take one waiting player within range, or join the pool. One decision.

        Taking and joining have to be the same step. Split in two, there are
        awaits in between, and two players arriving inside that window each
        see an empty pool, each sit down in it, and both wait out the full
        timeout standing right in front of the other. That is not theoretical:
        it is what broke the first four-player run against the containers,
        with 5ms between them.

        WATCH makes it atomic without a lock. If the pool changed between the
        read and the write, EXEC does nothing, and looking again is correct
        rather than merely safe -- the change is very often the opponent who
        just arrived.
        """
        async with self.redis.pipeline() as pipe:
            while True:
                try:
                    await pipe.watch(WAITING_BY_ELO)
                    candidates = await pipe.zrangebyscore(
                        WAITING_BY_ELO, elo - ELO_RANGE, elo + ELO_RANGE, withscores=True
                    )
                    opponent = next(
                        (
                            (name, int(score))
                            for name, score in candidates
                            if name != username
                        ),
                        None,
                    )

                    pipe.multi()
                    if opponent is not None:
                        pipe.zrem(WAITING_BY_ELO, opponent[0])
                        pipe.zrem(WAITING_BY_TIME, opponent[0])
                    else:
                        pipe.zadd(WAITING_BY_ELO, {username: elo})
                        pipe.zadd(WAITING_BY_TIME, {username: time.time()})
                    await pipe.execute()

                    return opponent
                except WatchError:
                    continue

    def _wake(self, opponent: str, username: str, elo: int) -> None:
        """Hand the result to the waiting coroutine, if it is in this process.

        LIMITATION -- this is why the deployment runs one gateway and many
        shards, rather than many of both. With two gateways, a player waiting
        on gateway A is claimed out of Redis by a player arriving at gateway
        B, and this call finds nothing to wake: the first waits out the full
        timeout and is told no opponent was found, while the second sits on a
        shard waiting for someone who never connects. Worse than a hang,
        because both sides look like ordinary outcomes.

        Server_Design.md 5.2.1 puts the fix on the event bus, which is stage
        4; a Redis queue would work too, but the bus is where the assignment
        message belongs anyway. The other half of that section -- expiring
        stale entries by timestamp so a dead process strands nobody -- is
        already done, in _drop_expired.
        """
        waiting = self._waiting.get(opponent)
        if waiting is not None:
            waiting.opponent = (username, elo)
            waiting.event.set()

    async def _enqueue(self, username: str, elo: int) -> None:
        await self.redis.zadd(WAITING_BY_ELO, {username: elo})
        await self.redis.zadd(WAITING_BY_TIME, {username: time.time()})

    async def _dequeue(self, username: str) -> None:
        await self.redis.zrem(WAITING_BY_ELO, username)
        await self.redis.zrem(WAITING_BY_TIME, username)

    async def _drop_expired(self) -> None:
        """Remove players who have been waiting past the timeout.

        Needed now that the pool outlives the process that filled it: a server
        killed mid-wait never runs its finally block, and its entries would sit
        in Redis forever. Any process can run this, removing an already-removed
        member is a no-op, so it needs no owner and no coordination.
        """
        cutoff = time.time() - MATCH_TIMEOUT_SECONDS
        expired = await self.redis.zrangebyscore(WAITING_BY_TIME, "-inf", cutoff)
        for username in expired:
            await self._dequeue(username)
