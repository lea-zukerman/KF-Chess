"""Shared server core: the pieces every role needs.

Running a game (match, commands), user data (db, elo) and pairing
(matchmaking, rooms). The processes that use these live in `services/`,
which imports from here; nothing here imports back.
"""
