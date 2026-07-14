class GameEngine:
    def __init__(self, board, rule_engine, arbiter):
        self.board = board
        self.rule_engine = rule_engine
        self.arbiter = arbiter

    def tick(self, ms):
        self.board.update_moves_by_time(ms)
