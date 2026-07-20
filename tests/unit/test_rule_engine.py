import unittest

from kungfu_chess.model.board import Board
from kungfu_chess.rules.rule_engine import RuleEngine


class RuleEngineTests(unittest.TestCase):
    def test_is_legal_for_white_pawn(self):
        board = Board.from_text_lines(['. .', 'wP .'])
        rule_engine = RuleEngine(board)

        self.assertTrue(rule_engine.is_legal(1, 0, 0, 0))
        self.assertFalse(rule_engine.is_legal(1, 0, 1, 0))


if __name__ == '__main__':
    unittest.main()
