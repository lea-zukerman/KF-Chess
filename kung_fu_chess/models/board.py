from .position import Position
from .piece import Piece
from ..constants import (
    NEW_LINE,
    VALID_PIECES,
    CELL_SIZE,
    MS_PER_CELL,
    JUMP_DURATION_MS,
    PIECE_COLORS,
)


class Board:
    def __init__(self, grid):
        self._grid = grid
        self._rows = len(grid)
        self._cols = len(grid[0]) if self._rows > 0 else 0
        self._selected_cell = None
        self._active_moves = []  # (from_row, from_col, to_row, to_col, piece_token, arrival_time)
        self._active_jumps = []  # (row, col, piece_token, end_time)
        self._game_over = False

    @classmethod
    def from_text_lines(cls, lines):
        if not lines:
            return None
        grid = [line.strip().split() for line in lines if line.strip()]
        if not grid:
            return None
            
        expected_cols = len(grid[0])
        for row in grid:
            if len(row) != expected_cols:
                return None
                
        for row in grid:
            for token in row:
                if token == '.':
                    continue
                if len(token) != 2 or token[0] not in PIECE_COLORS or token[1] not in VALID_PIECES:
                    return None
                    
        return cls(grid)

    def is_game_over(self) -> bool:
        return self._game_over

    def update_moves_by_time(self, current_time_ms: int):
        if self._game_over:
            return

        # 1. process arrivals and collisions
        self._active_moves.sort(key=lambda m: m[5])
        remaining_moves = []
        
        for move in self._active_moves:
            from_row, from_col, to_row, to_col, piece_token, arrival_time = move
            if current_time_ms >= arrival_time:
                airborne_piece = None
                for jump in self._active_jumps:
                    j_row, j_col, j_token, end_time = jump
                    if j_row == to_row and j_col == to_col and end_time >= arrival_time:
                        airborne_piece = jump
                        break
                
                if airborne_piece:
                    j_row, j_col, j_token, end_time = airborne_piece
                    if j_token[0] == piece_token[0]:
                        if self._grid[from_row][from_col] == '.':
                            self._grid[from_row][from_col] = piece_token
                    else:
                        self._grid[j_row][j_col] = j_token
                        self._active_jumps.remove(airborne_piece)
                    continue
                
                target_current = self._grid[to_row][to_col]
                if target_current != '.' and target_current[0] == piece_token[0]:
                    if self._grid[from_row][from_col] == '.':
                        self._grid[from_row][from_col] = piece_token
                else:
                    if target_current != '.' and target_current[1] == 'K':
                        self._game_over = True
                    
                    final_token = piece_token
                    if piece_token[1] == 'P':
                        if (piece_token[0] == 'w' and to_row == 0) or (piece_token[0] == 'b' and to_row == self._rows - 1):
                            final_token = piece_token[0] + 'Q'
                    
                    self._grid[to_row][to_col] = final_token
                    if self._game_over:
                        break
            else:
                remaining_moves.append(move)
                
        if not self._game_over:
            self._active_moves = remaining_moves
        else:
            self._active_moves = []
            self._active_jumps = []
            return

        # 2. finish jumps
        remaining_jumps = []
        for jump in self._active_jumps:
            j_row, j_col, j_token, end_time = jump
            if current_time_ms >= end_time:
                if self._grid[j_row][j_col] == '.':
                    self._grid[j_row][j_col] = j_token
            else:
                remaining_jumps.append(jump)
        self._active_jumps = remaining_jumps

    def handle_jump_command(self, x: int, y: int, current_time_ms: int):
        self.update_moves_by_time(current_time_ms)
        if self._game_over:
            return

        col = x // CELL_SIZE
        row = y // CELL_SIZE

        if not (0 <= row < self._rows and 0 <= col < self._cols):
            return

        selected_token = self._grid[row][col]
        if selected_token != '.':
            end_time = current_time_ms + JUMP_DURATION_MS
            self._active_jumps.append((row, col, selected_token, end_time))
            self._grid[row][col] = '.'
        self._selected_cell = None

    def _is_path_clear(self, from_row: int, from_col: int, to_row: int, to_col: int) -> bool:
        row_step = 0
        col_step = 0

        if to_row > from_row: row_step = 1
        elif to_row < from_row: row_step = -1

        if to_col > from_col: col_step = 1
        elif to_col < from_col: col_step = -1

        current_row = from_row + row_step
        current_col = from_col + col_step

        while (current_row, current_col) != (to_row, to_col):
            if self._grid[current_row][current_col] != '.':
                return False
            current_row += row_step
            current_col += col_step

        return True

    def _is_move_legal(self, selected_token: str, from_row: int, from_col: int, to_row: int, to_col: int) -> bool:
        piece_color = selected_token[0]
        piece_type = selected_token[1]
        
        dr = abs(to_row - from_row)
        dc = abs(to_col - from_col)

        if dr == 0 and dc == 0:
            return False

        target_token = self._grid[to_row][to_col]

        if piece_type == 'P':
            row_diff = to_row - from_row
            if piece_color == 'w' and row_diff >= 0: return False
            if piece_color == 'b' and row_diff <= 0: return False

            if dc == 0:
                if dr == 1:
                    return target_token == '.'
                elif dr == 2:
                    is_start_row = (piece_color == 'w' and from_row == self._rows - 1) or (piece_color == 'b' and from_row == 0)
                    if not is_start_row:
                        return False
                    middle_row = from_row + (row_diff // 2)
                    return self._grid[middle_row][from_col] == '.' and target_token == '.'
                return False

            if dc == 1 and dr == 1:
                return target_token != '.' and target_token[0] != piece_color
            return False

        if piece_type == 'K': return dr <= 1 and dc <= 1
        elif piece_type == 'R':
            if not (dr == 0 or dc == 0): return False
            return self._is_path_clear(from_row, from_col, to_row, to_col)
        elif piece_type == 'B':
            if dr != dc: return False
            return self._is_path_clear(from_row, from_col, to_row, to_col)
        elif piece_type == 'Q':
            if not (dr == 0 or dc == 0 or dr == dc): return False
            return self._is_path_clear(from_row, from_col, to_row, to_col)
        elif piece_type == 'N':
            return (dr == 1 and dc == 2) or (dr == 2 and dc == 1)

        return False

    def handle_click(self, x: int, y: int, current_time_ms: int):
        self.update_moves_by_time(current_time_ms)

        if self._game_over:
            return

        col = x // CELL_SIZE
        row = y // CELL_SIZE

        if not (0 <= row < self._rows and 0 <= col < self._cols):
            return

        clicked_token = self._grid[row][col]

        if self._selected_cell is None:
            if clicked_token != '.':
                if self._active_moves:
                    active_color = self._active_moves[0][4][0]
                    if clicked_token[0] != active_color:
                        return
                self._selected_cell = (row, col)
        else:
            sel_row, sel_col = self._selected_cell
            selected_token = self._grid[sel_row][sel_col]

            if (sel_row, sel_col) == (row, col):
                if selected_token != '.':
                    end_time = current_time_ms + JUMP_DURATION_MS
                    self._active_jumps.append((sel_row, sel_col, selected_token, end_time))
                    self._grid[sel_row][sel_col] = '.'
                self._selected_cell = None
            elif clicked_token != '.' and clicked_token[0] == selected_token[0]:
                self._selected_cell = (row, col)
            else:
                if self._is_move_legal(selected_token, sel_row, sel_col, row, col):
                    distance = max(abs(row - sel_row), abs(col - sel_col))
                    travel_time = distance * MS_PER_CELL
                    arrival_time = current_time_ms + travel_time
                    
                    self._active_moves.append((sel_row, sel_col, row, col, selected_token, arrival_time))
                    self._grid[sel_row][sel_col] = '.'
                    
                self._selected_cell = None

    def get_canonical_string(self, current_time_ms: int) -> str:
        self.update_moves_by_time(current_time_ms)
        
        display_grid = [row[:] for row in self._grid]
        
        for move in self._active_moves:
            from_row, from_col, to_row, to_col, piece_token, arrival_time = move
            display_grid[from_row][from_col] = piece_token
            
        for jump in self._active_jumps:
            j_row, j_col, j_token, end_time = jump
            display_grid[j_row][j_col] = j_token
            
        output_lines = []
        for row in display_grid:
            output_lines.append(" ".join(row))
        return NEW_LINE.join(output_lines)
