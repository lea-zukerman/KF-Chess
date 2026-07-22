from ..rules.rule_engine import RuleEngine
from ..realtime.real_time_arbiter import RealTimeArbiter
from ..input.controller import Controller
from ..input.board_mapper import screen_to_cell
from ..constants import CELL_SIZE


class GameEngine:
    """Orchestrates a Board through the rules/realtime/input layers.

    This is the entry point production code (io.board_parser) drives the
    game through, rather than talking to Board's internals directly.
    """

    def __init__(self, board, rule_engine=None, arbiter=None, controller=None):
        self.board = board
        self.rule_engine = rule_engine or RuleEngine(board)
        self.arbiter = arbiter or RealTimeArbiter()
        self.controller = controller or Controller()

    def tick(self, current_time_ms: int) -> None:
        self.arbiter.resolve(self.board, current_time_ms)

    def handle_click(self, x: int, y: int, current_time_ms: int, current_turn: str | None = None) -> bool:
        row, col = screen_to_cell(x, y, CELL_SIZE)
        return self.controller.handle_click_at_cell(self.board, row, col, current_time_ms, current_turn)

    def handle_jump(self, x: int, y: int, current_time_ms: int, current_turn: str | None = None) -> bool:
        row, col = screen_to_cell(x, y, CELL_SIZE)
        return self.controller.handle_jump_at_cell(self.board, row, col, current_time_ms, current_turn)

    def is_game_over(self) -> bool:
        return self.board.is_game_over()

    def resign(self, winner_color: str) -> None:
        self.board.resign(winner_color)

    def winner(self):
        return self.board.winner

    def get_board_string(self, current_time_ms: int) -> str:
        return self.board.get_canonical_string(current_time_ms)

    def get_move_log(self, current_time_ms: int) -> list[str]:
        self.tick(current_time_ms)
        return self.board.get_move_log()

    def get_score(self, current_time_ms: int) -> dict[str, int]:
        self.tick(current_time_ms)
        return self.board.get_score()
