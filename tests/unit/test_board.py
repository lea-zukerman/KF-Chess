import unittest

from kungfu_chess.model.board import Board
from kungfu_chess.view.game_app import create_default_board_text


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

    def test_handle_click_at_cell_only_allows_current_turn_piece(self):
        lines = ['wP .', 'bP .']
        board = Board.from_text_lines(lines)

        self.assertFalse(board.handle_click_at_cell(1, 0, 0, current_turn='w'))
        self.assertFalse(board.handle_click_at_cell(0, 0, 0, current_turn='b'))
        self.assertFalse(board.handle_click_at_cell(0, 0, 0, current_turn='w'))
        self.assertEqual(board._selected_cell, (0, 0))

    def test_handle_click_at_cell_allows_capture_of_enemy_piece(self):
        lines = ['bR . . .', '. . . .', '. . . .', 'wR . . .']
        board = Board.from_text_lines(lines)

        self.assertFalse(board.handle_click_at_cell(3, 0, 0, current_turn='w'))
        self.assertEqual(board._selected_cell, (3, 0))
        self.assertTrue(board.handle_click_at_cell(0, 0, 0, current_turn='w'))
        self.assertEqual(board._selected_cell, None)
        # Capture travels over time like any other move (3 cells * MS_PER_CELL)
        self.assertEqual(board.get_canonical_string(0), 'bR . . .\n. . . .\n. . . .\nwR . . .')
        self.assertEqual(board.get_canonical_string(3000), 'wR . . .\n. . . .\n. . . .\n. . . .')

    def test_handle_click_at_cell_computes_valid_moves_for_selected_piece(self):
        lines = ['. . . .', '. wR . .', '. . . .', '. . . .']
        board = Board.from_text_lines(lines)

        self.assertFalse(board.handle_click_at_cell(1, 1, 0, current_turn='w'))
        self.assertEqual(board._selected_cell, (1, 1))
        self.assertTrue((1, 1, 0, 1) in board._valid_moves)
        self.assertTrue((1, 1, 1, 0) in board._valid_moves)
        self.assertTrue((1, 1, 1, 2) in board._valid_moves)
        self.assertTrue((1, 1, 2, 1) in board._valid_moves)

    def test_handle_jump_at_cell_respects_current_turn(self):
        lines = ['wP .', 'bP .']
        board = Board.from_text_lines(lines)

        self.assertFalse(board.handle_jump_at_cell(1, 0, 0, current_turn='w'))
        self.assertTrue(board.handle_jump_at_cell(0, 0, 0, current_turn='w'))

    def test_landed_move_rests_and_then_blocks_reselection(self):
        lines = ['. .', 'wP .']
        board = Board.from_text_lines(lines)

        board.handle_click(0, 100, 0)
        board.handle_click(0, 0, 0)
        self.assertEqual(board.get_canonical_string(1000), 'wQ .\n. .')

        # Fresh off landing, the piece is resting -- the renderer would show
        # 'long_rest', and the piece can't be re-selected yet.
        self.assertEqual(board.resting_state(0, 0, 1000), 'long_rest')
        self.assertFalse(board.handle_click_at_cell(0, 0, 1000, current_turn='w'))
        self.assertIsNone(board._selected_cell)

        # Once the rest period has elapsed, it's usable again.
        self.assertIsNone(board.resting_state(0, 0, 2001))
        self.assertFalse(board.handle_click_at_cell(0, 0, 2001, current_turn='w'))
        self.assertEqual(board._selected_cell, (0, 0))

    def test_white_pawn_can_open_with_a_two_square_move_on_the_real_board(self):
        # Regression test: pawns sit one row in front of their own back
        # rank on a real board, not on the literal edge row, and the
        # opening double-step must work from there.
        board = Board.from_text_lines(create_default_board_text().split('\n'))

        board.handle_click_at_cell(6, 0, 0, current_turn='w')
        self.assertTrue(board.handle_click_at_cell(4, 0, 0, current_turn='w'))
        self.assertEqual(board._active_moves[0].to_row, 4)

    def test_black_pawn_can_open_with_a_two_square_move_on_the_real_board(self):
        board = Board.from_text_lines(create_default_board_text().split('\n'))

        board.handle_click_at_cell(1, 0, 0, current_turn='b')
        self.assertTrue(board.handle_click_at_cell(3, 0, 0, current_turn='b'))
        self.assertEqual(board._active_moves[0].to_row, 3)

    def test_resign_ends_the_game_for_the_remaining_color(self):
        lines = ['. .', '. .']
        board = Board.from_text_lines(lines)

        board.resign('w')

        self.assertTrue(board.is_game_over())
        self.assertEqual(board.winner, 'w')


if __name__ == '__main__':
    unittest.main()
