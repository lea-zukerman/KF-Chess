from dataclasses import dataclass

from ..constants import MS_PER_CELL, JUMP_DURATION_MS


@dataclass
class Move:
    from_row: int
    from_col: int
    to_row: int
    to_col: int
    piece_token: str
    arrival_time: int


@dataclass
class Jump:
    row: int
    col: int
    piece_token: str
    end_time: int


def travel_distance(from_row: int, from_col: int, to_row: int, to_col: int) -> int:
    return max(abs(to_row - from_row), abs(to_col - from_col))


def compute_arrival_time(from_row: int, from_col: int, to_row: int, to_col: int, current_time_ms: int) -> int:
    return current_time_ms + travel_distance(from_row, from_col, to_row, to_col) * MS_PER_CELL


def compute_jump_end_time(current_time_ms: int) -> int:
    return current_time_ms + JUMP_DURATION_MS
