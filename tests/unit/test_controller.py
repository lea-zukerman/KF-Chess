import unittest

from kungfu_chess.model.board import Board
from kungfu_chess.input.controller import Controller


class ControllerTests(unittest.TestCase):
    def test_clicking_empty_cell_with_no_selection_is_ignored(self):
        board = Board.from_text_lines(['. .', '. .'])
        controller = Controller()

        self.assertFalse(controller.handle_click_at_cell(board, 0, 0, 0))
        self.assertIsNone(board._selected_cell)

    def test_clicking_a_piece_selects_it(self):
        board = Board.from_text_lines(['. .', 'wP .'])
        controller = Controller()

        self.assertFalse(controller.handle_click_at_cell(board, 1, 0, 0))
        self.assertEqual(board._selected_cell, (1, 0))

    def test_clicking_another_friendly_piece_replaces_selection(self):
        board = Board.from_text_lines(['wR .', 'wP .'])
        controller = Controller()

        controller.handle_click_at_cell(board, 0, 0, 0)
        self.assertEqual(board._selected_cell, (0, 0))

        controller.handle_click_at_cell(board, 1, 0, 0)
        self.assertEqual(board._selected_cell, (1, 0))
        # No move was queued, just a re-selection.
        self.assertEqual(board._active_moves, [])

    def test_clicking_destination_sends_move_request(self):
        board = Board.from_text_lines(['. .', 'wP .'])
        controller = Controller()

        controller.handle_click_at_cell(board, 1, 0, 0)
        result = controller.handle_click_at_cell(board, 0, 0, 0)

        self.assertTrue(result)
        self.assertEqual(len(board._active_moves), 1)
        self.assertEqual(board._grid[1][0], '.')
        self.assertIsNone(board._selected_cell)

    def test_only_current_turn_piece_can_be_selected(self):
        board = Board.from_text_lines(['wP .', 'bP .'])
        controller = Controller()

        self.assertFalse(controller.handle_click_at_cell(board, 1, 0, 0, current_turn='w'))
        self.assertIsNone(board._selected_cell)

    def test_clicking_same_cell_as_selection_jumps_in_place(self):
        board = Board.from_text_lines(['. .', 'wP .'])
        controller = Controller()

        controller.handle_click_at_cell(board, 1, 0, 0)
        result = controller.handle_click_at_cell(board, 1, 0, 0)

        self.assertTrue(result)
        self.assertEqual(len(board._active_jumps), 1)
        self.assertEqual(board._grid[1][0], '.')

    def test_handle_jump_at_cell_queues_a_jump(self):
        board = Board.from_text_lines(['. .', 'wP .'])
        controller = Controller()

        self.assertTrue(controller.handle_jump_at_cell(board, 1, 0, 0))
        self.assertEqual(len(board._active_jumps), 1)
        self.assertEqual(board._grid[1][0], '.')

    def test_resting_piece_cannot_be_selected(self):
        board = Board.from_text_lines(['. .', 'wP .'])
        board._cooldowns[(1, 0)] = (500, 'long_rest')
        controller = Controller()

        self.assertFalse(controller.handle_click_at_cell(board, 1, 0, 100))
        self.assertIsNone(board._selected_cell)

    def test_piece_is_selectable_again_once_cooldown_expires(self):
        board = Board.from_text_lines(['. .', 'wP .'])
        board._cooldowns[(1, 0)] = (500, 'long_rest')
        controller = Controller()

        controller.handle_click_at_cell(board, 1, 0, 500)
        self.assertEqual(board._selected_cell, (1, 0))

    def test_resting_piece_cannot_be_reselected_over_another_selection(self):
        board = Board.from_text_lines(['wR .', 'wP .'])
        board._cooldowns[(1, 0)] = (500, 'long_rest')
        controller = Controller()

        controller.handle_click_at_cell(board, 0, 0, 100)
        self.assertEqual(board._selected_cell, (0, 0))

        controller.handle_click_at_cell(board, 1, 0, 100)
        # The resting piece must not steal the selection.
        self.assertEqual(board._selected_cell, (0, 0))

    def test_resting_piece_cannot_be_jumped(self):
        board = Board.from_text_lines(['. .', 'wP .'])
        board._cooldowns[(1, 0)] = (500, 'long_rest')
        controller = Controller()

        self.assertFalse(controller.handle_jump_at_cell(board, 1, 0, 100))
        self.assertEqual(board._active_jumps, [])

    def test_compute_valid_moves_for_rook(self):
        board = Board.from_text_lines(['. . . .', '. wR . .', '. . . .', '. . . .'])
        controller = Controller()

        moves = controller.compute_valid_moves(board, 1, 1)

        self.assertIn((1, 1, 0, 1), moves)
        self.assertIn((1, 1, 1, 0), moves)
        self.assertIn((1, 1, 1, 2), moves)
        self.assertIn((1, 1, 2, 1), moves)


if __name__ == '__main__':
    unittest.main()
