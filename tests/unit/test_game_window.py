import unittest
from unittest import mock

import cv2

from client.game_window import GameWindow
from protocol.messages import JumpCommand, MoveCommand, StateUpdate

BOARD = "\n".join([
    "bR bN bB bQ bK bB bN bR",
    "bP bP bP bP bP bP bP bP",
    ".  .  .  .  .  .  .  .",
    ".  .  .  .  .  .  .  .",
    ".  .  .  .  .  .  .  .",
    ".  .  .  .  .  .  .  .",
    "wP wP wP wP wP wP wP wP",
    "wR wN wB wQ wK wB wN wR",
])

CELL = 512 // 8  # 64px, matches the default board_size


def _state(turn="w"):
    return StateUpdate(board=BOARD, white_name="Alice", black_name="Bob",
                       white_elo=1200, black_elo=1200, score_w=0, score_b=0,
                       turn=turn, game_over=False, winner=None)


def _px(row, col):
    """Center pixel of a cell, for feeding to the mouse handler."""
    return col * CELL + CELL // 2, row * CELL + CELL // 2


class GameWindowTests(unittest.TestCase):
    def _window(self, role="w"):
        # Mock the renderer so construction needs no image assets on disk.
        with mock.patch("client.game_window.GameRenderer"):
            return GameWindow("unused/pieces", my_role=role, board_size=(512, 512))

    def test_apply_state_rebuilds_display_board(self):
        window = self._window()
        window.apply_state(_state())

        self.assertIsNotNone(window.board)
        self.assertEqual((window.board._rows, window.board._cols), (8, 8))

    def test_first_left_click_selects_source_without_emitting(self):
        window = self._window("w")
        window.apply_state(_state())

        x, y = _px(6, 4)  # e2
        window.on_mouse(cv2.EVENT_LBUTTONDOWN, x, y)

        self.assertEqual(window.selected, (6, 4))
        self.assertTrue(window.outgoing.empty())

    def test_two_left_clicks_emit_move_command(self):
        window = self._window("w")
        window.apply_state(_state())

        window.on_mouse(cv2.EVENT_LBUTTONDOWN, *_px(6, 4))  # select e2
        window.on_mouse(cv2.EVENT_LBUTTONDOWN, *_px(4, 4))  # move to e4

        self.assertEqual(window.outgoing.get_nowait(), MoveCommand("e2", "e4"))
        self.assertIsNone(window.selected)

    def test_right_click_emits_jump_command(self):
        window = self._window("w")
        window.apply_state(_state())

        window.on_mouse(cv2.EVENT_RBUTTONDOWN, *_px(4, 4))  # e4

        self.assertEqual(window.outgoing.get_nowait(), JumpCommand("e4"))

    def test_observer_emits_nothing(self):
        window = self._window("observer")
        window.apply_state(_state())

        window.on_mouse(cv2.EVENT_LBUTTONDOWN, *_px(6, 4))

        self.assertTrue(window.outgoing.empty())

    def test_clicks_before_first_state_are_ignored(self):
        window = self._window("w")  # no apply_state yet

        window.on_mouse(cv2.EVENT_LBUTTONDOWN, *_px(6, 4))

        self.assertIsNone(window.selected)
        self.assertTrue(window.outgoing.empty())


if __name__ == "__main__":
    unittest.main()
