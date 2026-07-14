import unittest

from kung_fu_chess.models.board import Board


class BoardModelTests(unittest.TestCase):
    def test_from_text_lines_valid(self):
        lines = ['. .', '. .']
        board = Board.from_text_lines(lines)

        self.assertIsNotNone(board)
        self.assertEqual(board._grid, [['.', '.'], ['.', '.']])

    def test_from_text_lines_invalid_token(self):
        lines = ['. X']
        board = Board.from_text_lines(lines)

        self.assertIsNone(board)

    def test_white_pawn_move_is_legal(self):
        lines = ['. .', 'wP .']
        board = Board.from_text_lines(lines)

        self.assertTrue(board._is_move_legal('wP', 1, 0, 0, 0))
        self.assertFalse(board._is_move_legal('wP', 1, 0, 1, 0))

    def test_handle_click_moves_pawn_after_wait(self):
        lines = ['. .', 'wP .']
        board = Board.from_text_lines(lines)

        board.handle_click(0, 100, 0)
        board.handle_click(0, 0, 0)

        self.assertEqual(board.get_canonical_string(0), '. .\nwP .')
        self.assertEqual(board.get_canonical_string(1000), 'wQ .\n. .')


if __name__ == '__main__':
    unittest.main()
