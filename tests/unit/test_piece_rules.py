import unittest

from kungfu_chess.rules.piece_rules import is_legal_move, is_path_clear


class PieceRulesTests(unittest.TestCase):
    def test_king_moves_one_cell_in_any_direction(self):
        grid = [['.', '.', '.'], ['.', 'wK', '.'], ['.', '.', '.']]

        self.assertTrue(is_legal_move('wK', 1, 1, 0, 0, grid))
        self.assertTrue(is_legal_move('wK', 1, 1, 2, 1, grid))

    def test_king_cannot_move_two_cells(self):
        grid = [['.', '.', '.'], ['.', '.', '.'], ['wK', '.', '.']]

        self.assertFalse(is_legal_move('wK', 2, 0, 0, 0, grid))

    def test_rook_moves_straight_only(self):
        grid = [['.', '.', '.'], ['.', '.', '.'], ['wR', '.', '.']]

        self.assertTrue(is_legal_move('wR', 2, 0, 0, 0, grid))
        self.assertFalse(is_legal_move('wR', 2, 0, 0, 2, grid))

    def test_rook_blocked_by_piece_in_path(self):
        grid = [['.', '.', '.'], ['wP', '.', '.'], ['wR', '.', '.']]

        self.assertFalse(is_legal_move('wR', 2, 0, 0, 0, grid))

    def test_bishop_moves_diagonally_and_is_blocked(self):
        grid = [['.', '.', '.'], ['.', '.', '.'], ['wB', '.', '.']]
        self.assertTrue(is_legal_move('wB', 2, 0, 0, 2, grid))

        grid_blocked = [['.', '.', '.'], ['.', 'wP', '.'], ['wB', '.', '.']]
        self.assertFalse(is_legal_move('wB', 2, 0, 0, 2, grid_blocked))

    def test_knight_jumps_over_blockers(self):
        grid = [['.', '.', '.'], ['wP', 'wP', '.'], ['wN', '.', '.']]

        self.assertTrue(is_legal_move('wN', 2, 0, 0, 1, grid))

    def test_knight_rejects_non_l_shape(self):
        grid = [['.', '.', '.'], ['.', '.', '.'], ['wN', '.', '.']]

        self.assertFalse(is_legal_move('wN', 2, 0, 1, 1, grid))

    def test_cannot_capture_own_color(self):
        grid = [['.', '.', '.'], ['.', '.', '.'], ['wR', 'wP', '.']]

        self.assertFalse(is_legal_move('wR', 2, 0, 2, 1, grid))

    def test_can_capture_enemy_piece(self):
        grid = [['.', '.', '.'], ['.', '.', '.'], ['wR', 'bP', '.']]

        self.assertTrue(is_legal_move('wR', 2, 0, 2, 1, grid))

    def test_white_pawn_moves_up_only(self):
        grid = [['.', '.'], ['.', '.'], ['wP', '.']]

        self.assertTrue(is_legal_move('wP', 2, 0, 1, 0, grid))
        self.assertFalse(is_legal_move('wP', 1, 0, 2, 0, grid))

    def test_black_pawn_moves_down_only(self):
        grid = [['bP', '.'], ['.', '.'], ['.', '.']]

        self.assertTrue(is_legal_move('bP', 0, 0, 1, 0, grid))
        self.assertFalse(is_legal_move('bP', 1, 0, 0, 0, grid))

    def test_black_pawn_two_cell_move_from_start_row(self):
        # Black's start row is one row in front of its own back rank (row 0).
        grid = [['.'], ['bP'], ['.'], ['.']]

        self.assertTrue(is_legal_move('bP', 1, 0, 3, 0, grid))
        # Having advanced past its start row, it can no longer double-step.
        self.assertFalse(is_legal_move('bP', 2, 0, 4, 0, [['.'], ['.'], ['bP'], ['.'], ['.']]))

    def test_pawn_cannot_capture_forward(self):
        grid = [['.', '.'], ['bP', '.'], ['wP', '.']]

        self.assertFalse(is_legal_move('wP', 2, 0, 1, 0, grid))

    def test_pawn_cannot_move_diagonally_onto_empty_cell(self):
        grid = [['.', '.'], ['.', '.'], ['wP', '.']]

        self.assertFalse(is_legal_move('wP', 2, 0, 1, 1, grid))

    def test_pawn_captures_diagonally_onto_enemy(self):
        grid = [['.', 'bP'], ['wP', '.']]

        self.assertTrue(is_legal_move('wP', 1, 0, 0, 1, grid))

    def test_pawn_two_cell_move_from_start_row_with_clear_path(self):
        # A pawn's start row sits one row in front of its own back rank
        # (row 3 here), not on the back rank itself (row 3 would be it).
        grid = [['.'], ['.'], ['wP'], ['.']]

        self.assertTrue(is_legal_move('wP', 2, 0, 0, 0, grid))

    def test_pawn_two_cell_move_illegal_outside_start_row(self):
        # Sitting on the back rank itself is one row too far back to be
        # the pawn's actual start row.
        grid = [['.'], ['.'], ['.'], ['wP']]

        self.assertFalse(is_legal_move('wP', 3, 0, 1, 0, grid))

    def test_pawn_two_cell_move_blocked_by_piece_in_between(self):
        grid = [['.'], ['bP'], ['wP'], ['.']]

        self.assertFalse(is_legal_move('wP', 2, 0, 0, 0, grid))

    def test_is_path_clear_true_when_no_blockers(self):
        grid = [['.', '.', '.'], ['.', '.', '.'], ['wR', '.', '.']]

        self.assertTrue(is_path_clear(grid, 2, 0, 0, 0))

    def test_is_path_clear_false_when_blocked(self):
        grid = [['.', '.', '.'], ['wP', '.', '.'], ['wR', '.', '.']]

        self.assertFalse(is_path_clear(grid, 2, 0, 0, 0))


if __name__ == '__main__':
    unittest.main()
