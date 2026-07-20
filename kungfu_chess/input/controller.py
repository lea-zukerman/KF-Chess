from ..realtime.motion import Move, Jump, compute_arrival_time, compute_jump_end_time
from ..rules.piece_rules import is_legal_move


class Controller:
    """Turns a clicked/jumped board cell into selection state or a queued Move/Jump.

    Click semantics: clicking a piece selects it; clicking an empty cell with
    nothing selected is a no-op; clicking another friendly piece replaces the
    selection; clicking any other cell sends a (possibly illegal, then
    ignored) move request from the selected piece.
    """

    def handle_click_at_cell(self, board, row: int, col: int, current_time_ms: int, current_turn: str | None = None) -> bool:
        board.update_moves_by_time(current_time_ms)
        if board._game_over:
            return False

        if not (0 <= row < board._rows and 0 <= col < board._cols):
            return False

        clicked_token = board._grid[row][col]

        if board._selected_cell is None:
            if clicked_token != '.':
                if current_turn is not None and clicked_token[0] != current_turn:
                    return False
                if board.is_resting(row, col, current_time_ms):
                    return False
                board._selected_cell = (row, col)
                board._valid_moves = self.compute_valid_moves(board, row, col)
            return False

        sel_row, sel_col = board._selected_cell
        selected_token = board._grid[sel_row][sel_col]

        if (sel_row, sel_col) == (row, col):
            board._selected_cell = None
            board._valid_moves = []
            if selected_token == '.':
                return False
            end_time = compute_jump_end_time(current_time_ms)
            board._active_jumps.append(Jump(sel_row, sel_col, selected_token, end_time))
            board._grid[sel_row][sel_col] = '.'
            return True

        if clicked_token != '.' and selected_token != '.' and clicked_token[0] == selected_token[0]:
            if board.is_resting(row, col, current_time_ms):
                return False
            board._selected_cell = (row, col)
            board._valid_moves = self.compute_valid_moves(board, row, col)
            return False

        if selected_token != '.' and is_legal_move(selected_token, sel_row, sel_col, row, col, board._grid):
            arrival_time = compute_arrival_time(sel_row, sel_col, row, col, current_time_ms)
            board._active_moves.append(Move(sel_row, sel_col, row, col, selected_token, arrival_time))
            board._grid[sel_row][sel_col] = '.'
            board._selected_cell = None
            board._valid_moves = []
            return True

        board._selected_cell = None
        board._valid_moves = []
        return False

    def handle_jump_at_cell(self, board, row: int, col: int, current_time_ms: int, current_turn: str | None = None) -> bool:
        board.update_moves_by_time(current_time_ms)
        if board._game_over:
            return False

        if not (0 <= row < board._rows and 0 <= col < board._cols):
            return False

        selected_token = board._grid[row][col]
        if selected_token == '.':
            board._selected_cell = None
            return False

        if current_turn is not None and selected_token[0] != current_turn:
            return False

        if board.is_resting(row, col, current_time_ms):
            return False

        end_time = compute_jump_end_time(current_time_ms)
        board._active_jumps.append(Jump(row, col, selected_token, end_time))
        board._grid[row][col] = '.'
        board._selected_cell = None
        return True

    @staticmethod
    def compute_valid_moves(board, row: int, col: int) -> list[tuple[int, int, int, int]]:
        selected_token = board._grid[row][col]
        valid_moves = []
        if selected_token == '.':
            return valid_moves

        for target_row in range(board._rows):
            for target_col in range(board._cols):
                if (target_row, target_col) == (row, col):
                    continue
                if is_legal_move(selected_token, row, col, target_row, target_col, board._grid):
                    valid_moves.append((row, col, target_row, target_col))
        return valid_moves
