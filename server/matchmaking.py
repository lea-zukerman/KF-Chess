import asyncio

ELO_RANGE = 100
MATCH_TIMEOUT_SECONDS = 60


class NoOpponentFound(Exception):
    pass


class _WaitingPlayer:
    def __init__(self, username, elo):
        self.username = username
        self.elo = elo
        self.opponent = None
        self.event = asyncio.Event()


class Matchmaker:
    def __init__(self):
        self._waiting = []

    async def find_match(self, username, elo):
        for candidate in self._waiting:
            if abs(candidate.elo - elo) <= ELO_RANGE:
                self._waiting.remove(candidate)
                candidate.opponent = (username, elo)
                candidate.event.set()
                return candidate.username, candidate.elo

        me = _WaitingPlayer(username, elo)
        self._waiting.append(me)
        try:
            await asyncio.wait_for(me.event.wait(), timeout=MATCH_TIMEOUT_SECONDS)
            return me.opponent
        except asyncio.TimeoutError:
            raise NoOpponentFound(username)
        finally:
            if me in self._waiting:
                self._waiting.remove(me)
