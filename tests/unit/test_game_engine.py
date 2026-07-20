import unittest

from kungfu_chess.model.board import Board
from kungfu_chess.engine.game_engine import GameEngine


class GameEngineTests(unittest.TestCase):
    def test_handle_click_selects_then_moves_piece(self):
        board = Board.from_text_lines(['. .', 'wP .'])
        engine = GameEngine(board)

        self.assertFalse(engine.handle_click(0, 100, 0))  # select
        self.assertTrue(engine.handle_click(0, 0, 0))      # move request

        self.assertEqual(engine.get_board_string(0), '. .\nwP .')
        self.assertEqual(engine.get_board_string(1000), 'wQ .\n. .')

    def test_handle_jump_queues_a_jump(self):
        board = Board.from_text_lines(['. .', 'wP .'])
        engine = GameEngine(board)

        self.assertTrue(engine.handle_jump(0, 100, 0))

        self.assertEqual(len(board._active_jumps), 1)
        self.assertEqual(board._grid[1][0], '.')

    def test_tick_advances_queued_moves(self):
        board = Board.from_text_lines(['. .', 'wP .'])
        engine = GameEngine(board)
        engine.handle_click(0, 100, 0)
        engine.handle_click(0, 0, 0)

        engine.tick(1000)

        self.assertEqual(board._grid[0][0], 'wQ')

    def test_is_game_over_reflects_king_capture(self):
        board = Board.from_text_lines(['bK .', 'wR .'])
        engine = GameEngine(board)

        engine.handle_click(0, 100, 0)  # select wR
        engine.handle_click(0, 0, 0)    # move onto bK

        engine.tick(1000)

        self.assertTrue(engine.is_game_over())


if __name__ == '__main__':
    unittest.main()
