class GameState:
    def __init__(self):
        self.current_turn = 'w'
        self.move_history = []

    def switch_turn(self):
        self.current_turn = 'b' if self.current_turn == 'w' else 'w'

    def record_move(self, move):
        self.move_history.append(move)
