def is_path_clear(grid, from_row: int, from_col: int, to_row: int, to_col: int) -> bool:
    row_step = 0
    col_step = 0

    if to_row > from_row: row_step = 1
    elif to_row < from_row: row_step = -1

    if to_col > from_col: col_step = 1
    elif to_col < from_col: col_step = -1

    current_row = from_row + row_step
    current_col = from_col + col_step

    while (current_row, current_col) != (to_row, to_col):
        if grid[current_row][current_col] != '.':
            return False
        current_row += row_step
        current_col += col_step

    return True


def _pawn_rule(piece_color, dr, dc, from_row, from_col, to_row, to_col, grid, rows, target_token):
    row_diff = to_row - from_row
    if piece_color == 'w' and row_diff >= 0:
        return False
    if piece_color == 'b' and row_diff <= 0:
        return False

    if dc == 0:
        if dr == 1:
            return target_token == '.'
        if dr == 2:
            # A pawn's start row is one row in front of its own back
            # rank (rows - 1 for white, 0 for black), not the back rank
            # itself.
            is_start_row = (piece_color == 'w' and from_row == rows - 2) or (piece_color == 'b' and from_row == 1)
            if not is_start_row:
                return False
            middle_row = from_row + (row_diff // 2)
            return grid[middle_row][from_col] == '.' and target_token == '.'
        return False

    if dc == 1 and dr == 1:
        return target_token != '.' and target_token[0] != piece_color
    return False


def _king_rule(piece_color, dr, dc, from_row, from_col, to_row, to_col, grid, rows, target_token):
    return dr <= 1 and dc <= 1


def _rook_rule(piece_color, dr, dc, from_row, from_col, to_row, to_col, grid, rows, target_token):
    if not (dr == 0 or dc == 0):
        return False
    return is_path_clear(grid, from_row, from_col, to_row, to_col)


def _bishop_rule(piece_color, dr, dc, from_row, from_col, to_row, to_col, grid, rows, target_token):
    if dr != dc:
        return False
    return is_path_clear(grid, from_row, from_col, to_row, to_col)


def _queen_rule(piece_color, dr, dc, from_row, from_col, to_row, to_col, grid, rows, target_token):
    if not (dr == 0 or dc == 0 or dr == dc):
        return False
    return is_path_clear(grid, from_row, from_col, to_row, to_col)


def _knight_rule(piece_color, dr, dc, from_row, from_col, to_row, to_col, grid, rows, target_token):
    return (dr == 1 and dc == 2) or (dr == 2 and dc == 1)


PIECE_RULES = {
    'P': _pawn_rule,
    'K': _king_rule,
    'R': _rook_rule,
    'B': _bishop_rule,
    'Q': _queen_rule,
    'N': _knight_rule,
}


def is_legal_move(selected_token: str, from_row: int, from_col: int, to_row: int, to_col: int, grid) -> bool:
    piece_color = selected_token[0]
    piece_type = selected_token[1]
    rows = len(grid)

    dr = abs(to_row - from_row)
    dc = abs(to_col - from_col)

    if dr == 0 and dc == 0:
        return False

    target_token = grid[to_row][to_col]

    if target_token != '.' and target_token[0] == piece_color:
        return False

    rule = PIECE_RULES.get(piece_type)
    if rule is None:
        return False
    return rule(piece_color, dr, dc, from_row, from_col, to_row, to_col, grid, rows, target_token)


def legal_piece_moves(piece_token, from_row, from_col, board):
    valid_moves = []
    grid = board._grid
    for target_row in range(board._rows):
        for target_col in range(board._cols):
            if (target_row, target_col) == (from_row, from_col):
                continue
            if is_legal_move(piece_token, from_row, from_col, target_row, target_col, grid):
                valid_moves.append((from_row, from_col, target_row, target_col))
    return valid_moves
