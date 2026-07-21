def cell_to_algebraic(row: int, col: int, board_rows: int) -> str:
    file = chr(ord('a') + col)
    rank = board_rows - row
    return f"{file}{rank}"


def algebraic_to_cell(square: str, board_rows: int) -> tuple[int, int]:
    """Inverse of cell_to_algebraic. Raises ValueError for malformed input."""
    if len(square) < 2:
        raise ValueError(f"Invalid square: {square!r}")

    file, rank_str = square[0], square[1:]
    col = ord(file) - ord('a')
    try:
        rank = int(rank_str)
    except ValueError:
        raise ValueError(f"Invalid square: {square!r}") from None

    row = board_rows - rank
    return row, col
