from ..engine.game_engine import GameEngine
from ..bus.event_bus import EventBus


class GameSession:
    """Owns one GameEngine and publishes what changed after each command.

    This is the thing a transport (WebSocket server, or any future caller)
    talks to instead of Board or GameEngine directly: it takes cell-based
    move/jump requests and a clock tick, and turns the resulting state
    changes into bus events (`game_started`, `move_logged`, `score_changed`,
    `game_over`) without changing GameEngine/Board/rules/realtime at all.
    """

    def __init__(self, board, bus: EventBus):
        self.engine = GameEngine(board)
        self.bus = bus
        self._last_log_len = 0
        self._last_score = {"w": 0, "b": 0}
        self._game_over_fired = False
        self.bus.publish("game_started", {})

    def request_move(
        self,
        from_row: int,
        from_col: int,
        to_row: int,
        to_col: int,
        current_time_ms: int,
        current_turn: str | None = None,
    ) -> bool:
        board = self.engine.board
        board.update_moves_by_time(current_time_ms)
        board.handle_click_at_cell(from_row, from_col, current_time_ms, current_turn)
        if board.selected_cell != (from_row, from_col):
            return False
        accepted = board.handle_click_at_cell(to_row, to_col, current_time_ms, current_turn)
        self._publish_diff(current_time_ms)
        return accepted

    def request_jump(
        self,
        row: int,
        col: int,
        current_time_ms: int,
        current_turn: str | None = None,
    ) -> bool:
        accepted = self.engine.board.handle_jump_at_cell(row, col, current_time_ms, current_turn)
        self._publish_diff(current_time_ms)
        return accepted

    def tick(self, current_time_ms: int) -> None:
        self.engine.tick(current_time_ms)
        self._publish_diff(current_time_ms)

    def snapshot(self, current_time_ms: int) -> dict:
        return {
            "board": self.engine.get_board_string(current_time_ms),
            "score": self.engine.get_score(current_time_ms),
            "move_log": self.engine.get_move_log(current_time_ms),
            "game_over": self.engine.is_game_over(),
        }

    def _publish_diff(self, current_time_ms: int) -> None:
        move_log = self.engine.get_move_log(current_time_ms)
        for entry in move_log[self._last_log_len:]:
            self.bus.publish("move_logged", {"entry": entry})
        self._last_log_len = len(move_log)

        score = self.engine.get_score(current_time_ms)
        if score != self._last_score:
            self.bus.publish("score_changed", {"score": score})
            self._last_score = score

        if self.engine.is_game_over() and not self._game_over_fired:
            self._game_over_fired = True
            self.bus.publish("game_over", {})
