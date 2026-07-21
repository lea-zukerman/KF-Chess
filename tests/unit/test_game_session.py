import unittest

from kungfu_chess.model.board import Board
from kungfu_chess.bus.event_bus import EventBus
from kungfu_chess.app.game_session import GameSession


class GameSessionTests(unittest.TestCase):
    def test_game_started_event_fires_on_construction(self):
        board = Board.from_text_lines(['. .', 'wP .'])
        bus = EventBus()
        events = []
        bus.subscribe('game_started', events.append)

        GameSession(board, bus)

        self.assertEqual(events, [{}])

    def test_request_move_fires_move_logged_on_arrival(self):
        board = Board.from_text_lines(['. .', 'wP .'])
        bus = EventBus()
        logged = []
        bus.subscribe('move_logged', lambda payload: logged.append(payload['entry']))

        session = GameSession(board, bus)
        self.assertTrue(session.request_move(1, 0, 0, 0, 0))

        # Move hasn't arrived yet at time 0.
        self.assertEqual(logged, [])

        session.tick(1000)

        self.assertEqual(len(logged), 1)
        self.assertIn('wP', logged[0])

    def test_capture_fires_score_changed(self):
        board = Board.from_text_lines(['bP .', 'wR .'])
        bus = EventBus()
        scores = []
        bus.subscribe('score_changed', lambda payload: scores.append(payload['score']))

        session = GameSession(board, bus)
        session.request_move(1, 0, 0, 0, 0)
        session.tick(1000)

        self.assertEqual(scores[-1], {'w': 1, 'b': 0})

    def test_game_over_fires_exactly_once(self):
        board = Board.from_text_lines(['bK .', 'wR .'])
        bus = EventBus()
        game_overs = []
        bus.subscribe('game_over', game_overs.append)

        session = GameSession(board, bus)
        session.request_move(1, 0, 0, 0, 0)
        session.tick(1000)
        session.tick(2000)  # should not refire

        self.assertEqual(len(game_overs), 1)

    def test_request_jump_returns_false_for_empty_cell(self):
        board = Board.from_text_lines(['. .', 'wP .'])
        bus = EventBus()

        session = GameSession(board, bus)

        self.assertFalse(session.request_jump(0, 0, 0))


if __name__ == '__main__':
    unittest.main()
