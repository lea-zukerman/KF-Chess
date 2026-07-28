import unittest
from unittest import mock

from client import incoming
from client.incoming import EnterContext, HandshakeFailed
from protocol.messages import (
    AuthError,
    ErrorMessage,
    LoggedIn,
    MoveRejected,
    ResignCountdown,
    RoleAssigned,
    RoomCreated,
    SearchingForOpponent,
    StateUpdate,
)


def _state():
    return StateUpdate(board="x", white_name="a", black_name="b",
                       white_elo=1200, black_elo=1200, score_w=0, score_b=0,
                       turn="w", game_over=False)


class FakeWindow:
    def __init__(self):
        self.applied = None
        self.status = None

    def apply_state(self, message):
        self.applied = message

    def set_status(self, text):
        self.status = text


class LoginDispatchTests(unittest.TestCase):
    def test_logged_in_is_authenticated(self):
        self.assertEqual(incoming.dispatch_login(LoggedIn()), (True, ""))

    def test_auth_error_carries_reason(self):
        self.assertEqual(incoming.dispatch_login(AuthError("INVALID_CREDENTIALS")),
                         (False, "INVALID_CREDENTIALS"))

    def test_unexpected_reply_is_a_failure(self):
        self.assertEqual(incoming.dispatch_login(object()), (False, "unexpected response"))


class EnterDispatchTests(unittest.TestCase):
    def test_role_assigned_is_terminal(self):
        self.assertEqual(incoming.dispatch_enter(EnterContext(), RoleAssigned("b")), ("b", None))

    def test_searching_keeps_waiting(self):
        self.assertIsNone(incoming.dispatch_enter(EnterContext(), SearchingForOpponent()))

    def test_room_created_stores_id_and_keeps_waiting(self):
        ctx = EnterContext()
        with mock.patch.object(incoming, "messagebox"):
            result = incoming.dispatch_enter(ctx, RoomCreated("K7QX"))
        self.assertIsNone(result)
        self.assertEqual(ctx.created_room_id, "K7QX")

    def test_role_after_room_carries_the_room_id(self):
        ctx = EnterContext()
        with mock.patch.object(incoming, "messagebox"):
            incoming.dispatch_enter(ctx, RoomCreated("K7QX"))
        self.assertEqual(incoming.dispatch_enter(ctx, RoleAssigned("w")), ("w", "K7QX"))

    def test_error_message_raises(self):
        with self.assertRaises(HandshakeFailed):
            incoming.dispatch_enter(EnterContext(), ErrorMessage("ROOM_NOT_FOUND"))

    def test_unknown_message_keeps_waiting(self):
        self.assertIsNone(incoming.dispatch_enter(EnterContext(), object()))


class GameDispatchTests(unittest.TestCase):
    def test_state_update_is_applied(self):
        window = FakeWindow()
        state = _state()
        incoming.dispatch_game(window, state)
        self.assertIs(window.applied, state)

    def test_move_rejected_sets_status(self):
        window = FakeWindow()
        incoming.dispatch_game(window, MoveRejected("ILLEGAL_MOVE"))
        self.assertIn("ILLEGAL_MOVE", window.status)

    def test_resign_countdown_sets_status(self):
        window = FakeWindow()
        incoming.dispatch_game(window, ResignCountdown(5))
        self.assertIn("5", window.status)

    def test_unknown_message_is_ignored(self):
        window = FakeWindow()
        incoming.dispatch_game(window, RoleAssigned("w"))
        self.assertIsNone(window.applied)
        self.assertIsNone(window.status)


if __name__ == "__main__":
    unittest.main()
