import unittest

from kungfu_chess.model.position import Position


class PositionTests(unittest.TestCase):
    def test_stores_row_and_col(self):
        pos = Position(2, 5)

        self.assertEqual(pos.row, 2)
        self.assertEqual(pos.col, 5)

    def test_unpacks_as_row_col_tuple(self):
        pos = Position(3, 4)

        row, col = pos

        self.assertEqual((row, col), (3, 4))

    def test_repr_includes_row_and_col(self):
        pos = Position(1, 2)

        self.assertEqual(repr(pos), "Position(1, 2)")


if __name__ == '__main__':
    unittest.main()
