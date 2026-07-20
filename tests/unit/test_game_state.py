import unittest

from kungfu_chess.model.game_state import GameState


class GameStateTests(unittest.TestCase):
    def test_defaults_to_white_and_black(self):
        state = GameState()
        self.assertEqual(state.white_name, 'White')
        self.assertEqual(state.black_name, 'Black')
        self.assertEqual(state.current_player_name(), 'White')

    def test_custom_names_are_used_for_current_player(self):
        state = GameState(white_name='Alice', black_name='Bob')
        self.assertEqual(state.current_player_name(), 'Alice')

        state.switch_turn()
        self.assertEqual(state.current_player_name(), 'Bob')

    def test_switch_turn_toggles_between_colors(self):
        state = GameState()
        self.assertEqual(state.current_turn, 'w')

        state.switch_turn()
        self.assertEqual(state.current_turn, 'b')

        state.switch_turn()
        self.assertEqual(state.current_turn, 'w')


if __name__ == '__main__':
    unittest.main()
