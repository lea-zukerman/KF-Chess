from .position import Position
from .piece import Piece
from ..constants import (
    NEW_LINE,
    VALID_PIECES,
    CELL_SIZE,
    PIECE_COLORS,
    PIECE_VALUES,
)
from ..rules.piece_rules import is_legal_move, is_path_clear
from ..realtime.real_time_arbiter import RealTimeArbiter
from ..input.controller import Controller
from ..input.board_mapper import screen_to_cell


class Board:
    """Grid state and move/jump queues.

    Board itself only holds data; move legality lives in
    kungfu_chess.rules, move/jump timing and collisions live in
    kungfu_chess.realtime, and click/jump interpretation lives in
    kungfu_chess.input. Board delegates to those layers so each is
    independently unit-testable.
    """

    def __init__(self, grid):
        self._grid = grid
        self._rows = len(grid)
        self._cols = len(grid[0]) if self._rows > 0 else 0
        self._selected_cell = None
        self._valid_moves = []  # List of (from_row, from_col, to_row, to_col)
        self._active_moves = []  # list[realtime.motion.Move]
        self._active_jumps = []  # list[realtime.motion.Jump]
        self._game_over = False
        self._winner = None
        self._arbiter = RealTimeArbiter()
        self._controller = Controller()
        self._move_log = []  # list[str] of resolved move descriptions
        self._captured = {'w': [], 'b': []}  # color -> list of captured piece tokens
        self._cooldowns = {}  # (row, col) -> (ms timestamp resting until, rest state name)

    @property
    def rows(self) -> int:
        return self._rows

    @property
    def cols(self) -> int:
        return self._cols

    @property
    def selected_cell(self):
        return self._selected_cell

    @property
    def winner(self):
        return self._winner

    def is_resting(self, row: int, col: int, current_time_ms: int) -> bool:
        until_ms, _state = self._cooldowns.get((row, col), (0, None))
        return current_time_ms < until_ms

    def resting_state(self, row: int, col: int, current_time_ms: int):
        """The rest animation state ('short_rest'/'long_rest') a cell should
        currently show, or None if it isn't resting."""
        if not self.is_resting(row, col, current_time_ms):
            return None
        return self._cooldowns[(row, col)][1]

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

    def resign(self, winner_color: str) -> None:
        """End the game by resignation/disconnection rather than capture.

        winner_color is the color that remains -- the opponent of whoever
        resigned/disconnected.
        """
        self._game_over = True
        self._winner = winner_color

    def get_move_log(self) -> list[str]:
        return list(self._move_log)

    def get_score(self) -> dict[str, int]:
        return {
            color: sum(PIECE_VALUES[token[1]] for token in tokens)
            for color, tokens in self._captured.items()
        }

    def update_moves_by_time(self, current_time_ms: int):
        self._arbiter.resolve(self, current_time_ms)

    def handle_jump_at_cell(self, row: int, col: int, current_time_ms: int, current_turn: str | None = None) -> bool:
        return self._controller.handle_jump_at_cell(self, row, col, current_time_ms, current_turn)

    def handle_jump_command(self, x: int, y: int, current_time_ms: int, current_turn: str | None = None) -> bool:
        row, col = screen_to_cell(x, y, CELL_SIZE)
        return self.handle_jump_at_cell(row, col, current_time_ms, current_turn)

    def handle_click_at_cell(self, row: int, col: int, current_time_ms: int, current_turn: str | None = None) -> bool:
        return self._controller.handle_click_at_cell(self, row, col, current_time_ms, current_turn)

    def handle_click(self, x: int, y: int, current_time_ms: int, current_turn: str | None = None) -> bool:
        row, col = screen_to_cell(x, y, CELL_SIZE)
        return self.handle_click_at_cell(row, col, current_time_ms, current_turn)

    def _is_path_clear(self, from_row: int, from_col: int, to_row: int, to_col: int) -> bool:
        return is_path_clear(self._grid, from_row, from_col, to_row, to_col)

    def _is_move_legal(self, selected_token: str, from_row: int, from_col: int, to_row: int, to_col: int) -> bool:
        return is_legal_move(selected_token, from_row, from_col, to_row, to_col, self._grid)

    def get_canonical_string(self, current_time_ms: int) -> str:
        self.update_moves_by_time(current_time_ms)

        display_grid = [row[:] for row in self._grid]

        for move in self._active_moves:
            display_grid[move.from_row][move.from_col] = move.piece_token

        for jump in self._active_jumps:
            display_grid[jump.row][jump.col] = jump.piece_token

        output_lines = []
        for row in display_grid:
            output_lines.append(" ".join(row))
        return NEW_LINE.join(output_lines)
