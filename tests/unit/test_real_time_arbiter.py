import unittest

from kungfu_chess.constants import SHORT_REST_MS, LONG_REST_MS
from kungfu_chess.model.board import Board
from kungfu_chess.realtime.motion import Move, Jump
from kungfu_chess.realtime.real_time_arbiter import RealTimeArbiter


class RealTimeArbiterTests(unittest.TestCase):
    def test_move_stays_at_origin_before_arrival(self):
        board = Board.from_text_lines(['. .', 'wP .'])
        board._active_moves.append(Move(1, 0, 0, 0, 'wP', 1000))
        board._grid[1][0] = '.'

        arbiter = RealTimeArbiter()
        arbiter.resolve(board, 500)

        self.assertEqual(board._grid, [['.', '.'], ['.', '.']])
        self.assertEqual(len(board._active_moves), 1)

    def test_move_lands_at_destination_on_arrival(self):
        board = Board.from_text_lines(['. .', 'wP .'])
        board._active_moves.append(Move(1, 0, 0, 0, 'wP', 1000))
        board._grid[1][0] = '.'

        arbiter = RealTimeArbiter()
        arbiter.resolve(board, 1000)

        # Landing on row 0 promotes the pawn to a queen.
        self.assertEqual(board._grid, [['wQ', '.'], ['.', '.']])
        self.assertEqual(board._active_moves, [])

    def test_friendly_piece_at_destination_bounces_move_back(self):
        board = Board.from_text_lines(['wR .', 'wP .'])
        board._active_moves.append(Move(1, 0, 0, 0, 'wP', 1000))
        board._grid[1][0] = '.'

        arbiter = RealTimeArbiter()
        arbiter.resolve(board, 1000)

        self.assertEqual(board._grid[1][0], 'wP')
        self.assertEqual(board._grid[0][0], 'wR')

    def test_capturing_enemy_king_ends_game(self):
        board = Board.from_text_lines(['bK .', 'wR .'])
        board._active_moves.append(Move(1, 0, 0, 0, 'wR', 1000))
        board._grid[1][0] = '.'

        arbiter = RealTimeArbiter()
        arbiter.resolve(board, 1000)

        self.assertTrue(board._game_over)
        self.assertEqual(board._grid[0][0], 'wR')

    def test_pawn_promotes_to_queen_on_last_row(self):
        board = Board.from_text_lines(['. .', 'wP .'])
        board._active_moves.append(Move(1, 0, 0, 0, 'wP', 1000))
        board._grid[1][0] = '.'

        arbiter = RealTimeArbiter()
        arbiter.resolve(board, 1000)

        self.assertEqual(board._grid[0][0], 'wQ')

    def test_jump_lands_normally_when_no_enemy_arrives(self):
        board = Board.from_text_lines(['. .', 'wP .'])
        board._active_jumps.append(Jump(1, 0, 'wP', 1000))
        board._grid[1][0] = '.'

        arbiter = RealTimeArbiter()
        arbiter.resolve(board, 1000)

        self.assertEqual(board._grid[1][0], 'wP')
        self.assertEqual(board._active_jumps, [])

    def test_airborne_piece_captures_arriving_enemy(self):
        board = Board.from_text_lines(['. .', 'wP .', 'bR .'])
        board._active_jumps.append(Jump(1, 0, 'wP', 1000))
        board._grid[1][0] = '.'
        board._active_moves.append(Move(2, 0, 1, 0, 'bR', 500))
        board._grid[2][0] = '.'

        arbiter = RealTimeArbiter()
        arbiter.resolve(board, 500)

        # The airborne piece captures the arriving enemy immediately and
        # stays on its own cell; the enemy mover is removed entirely.
        self.assertEqual(board._grid[1][0], 'wP')
        self.assertEqual(board._active_jumps, [])
        self.assertEqual(board._grid[2][0], '.')
        self.assertEqual(board.get_score(), {'w': 5, 'b': 0})

    def test_move_without_capture_is_logged_but_scoreless(self):
        board = Board.from_text_lines(['. .', 'wP .'])
        board._active_moves.append(Move(1, 0, 0, 0, 'wP', 1000))
        board._grid[1][0] = '.'

        arbiter = RealTimeArbiter()
        arbiter.resolve(board, 1000)

        self.assertEqual(board.get_move_log(), ['wP a1-a2'])
        self.assertEqual(board.get_score(), {'w': 0, 'b': 0})

    def test_capturing_move_updates_log_and_score(self):
        board = Board.from_text_lines(['bN .', 'wR .'])
        board._active_moves.append(Move(1, 0, 0, 0, 'wR', 1000))
        board._grid[1][0] = '.'

        arbiter = RealTimeArbiter()
        arbiter.resolve(board, 1000)

        self.assertEqual(board.get_move_log(), ['wR a1-a2 xbN'])
        self.assertEqual(board.get_score(), {'w': 3, 'b': 0})

    def test_capturing_enemy_king_still_records_capture(self):
        board = Board.from_text_lines(['bK .', 'wR .'])
        board._active_moves.append(Move(1, 0, 0, 0, 'wR', 1000))
        board._grid[1][0] = '.'

        arbiter = RealTimeArbiter()
        arbiter.resolve(board, 1000)

        self.assertEqual(board.get_move_log(), ['wR a1-a2 xbK'])
        self.assertEqual(board.get_score(), {'w': 0, 'b': 0})

    def test_bounced_move_reclaims_home_from_an_enemy_instead_of_vanishing(self):
        # wN tries to move to (0,0) but wR already sits there (friendly) so
        # it must bounce home to (1,0) -- except bB got there first, having
        # arrived earlier in the same resolve() call. Previously the knight
        # was silently deleted; it must now capture the intruder instead.
        board = Board.from_text_lines(['wR', 'wN', 'bB'])
        board._grid[1][0] = '.'
        board._grid[2][0] = '.'
        board._active_moves.append(Move(1, 0, 0, 0, 'wN', 1000))
        board._active_moves.append(Move(2, 0, 1, 0, 'bB', 500))

        arbiter = RealTimeArbiter()
        arbiter.resolve(board, 1000)

        self.assertEqual(board._grid, [['wR'], ['wN'], ['.']])
        self.assertEqual(board._active_moves, [])
        self.assertEqual(board.get_move_log(), ['bB a1-a2', 'wN holds a2 xbB'])
        self.assertEqual(board.get_score(), {'w': 3, 'b': 0})

    def test_bounced_move_waits_when_home_still_held_by_a_friendly(self):
        # wN is "in flight" back to (1,0), but a friendly bishop already
        # occupies it. It must keep waiting, not disappear.
        board = Board.from_text_lines(['wR', 'wB'])
        move = Move(1, 0, 0, 0, 'wN', 1000)
        board._active_moves.append(move)

        arbiter = RealTimeArbiter()
        arbiter.resolve(board, 1000)

        self.assertEqual(board._grid, [['wR'], ['wB']])
        self.assertEqual(board._active_moves, [move])
        self.assertEqual(board.get_move_log(), [])

    def test_two_enemy_pieces_arriving_at_the_same_cell_mutually_destroy(self):
        board = Board.from_text_lines(['. . .'])
        board._active_moves.append(Move(0, 0, 0, 1, 'wN', 1000))
        board._active_moves.append(Move(0, 2, 0, 1, 'bN', 1000))

        arbiter = RealTimeArbiter()
        arbiter.resolve(board, 1000)

        self.assertEqual(board._grid, [['.', '.', '.']])
        self.assertEqual(board._active_moves, [])
        self.assertEqual(board.get_score(), {'w': 3, 'b': 3})
        self.assertEqual(len(board.get_move_log()), 1)
        self.assertIn('collision', board.get_move_log()[0])

    def test_same_color_pieces_racing_for_a_cell_the_rest_bounce_home(self):
        board = Board.from_text_lines(['. . .'])
        board._active_moves.append(Move(0, 0, 0, 1, 'wN', 1000))
        board._active_moves.append(Move(0, 2, 0, 1, 'wB', 1000))

        arbiter = RealTimeArbiter()
        arbiter.resolve(board, 1000)

        # The first-queued mover claims the square; the other returns home.
        self.assertEqual(board._grid, [['.', 'wN', 'wB']])
        self.assertEqual(board._active_moves, [])

    def test_landing_move_sets_a_long_rest_cooldown(self):
        board = Board.from_text_lines(['. .', 'wP .'])
        board._active_moves.append(Move(1, 0, 0, 0, 'wP', 1000))
        board._grid[1][0] = '.'

        arbiter = RealTimeArbiter()
        arbiter.resolve(board, 1000)

        self.assertTrue(board.is_resting(0, 0, 1000 + LONG_REST_MS - 1))
        self.assertFalse(board.is_resting(0, 0, 1000 + LONG_REST_MS))

    def test_landing_jump_sets_a_short_rest_cooldown(self):
        board = Board.from_text_lines(['. .', 'wP .'])
        board._active_jumps.append(Jump(1, 0, 'wP', 1000))
        board._grid[1][0] = '.'

        arbiter = RealTimeArbiter()
        arbiter.resolve(board, 1000)

        self.assertTrue(board.is_resting(1, 0, 1000 + SHORT_REST_MS - 1))
        self.assertFalse(board.is_resting(1, 0, 1000 + SHORT_REST_MS))

    def test_bouncing_home_without_a_fight_sets_no_cooldown(self):
        board = Board.from_text_lines(['wR .', 'wP .'])
        board._active_moves.append(Move(1, 0, 0, 0, 'wP', 1000))
        board._grid[1][0] = '.'

        arbiter = RealTimeArbiter()
        arbiter.resolve(board, 1000)

        self.assertFalse(board.is_resting(1, 0, 1000))


if __name__ == '__main__':
    unittest.main()
