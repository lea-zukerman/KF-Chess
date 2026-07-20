import unittest

from kungfu_chess.input.board_mapper import screen_to_cell


class BoardMapperTests(unittest.TestCase):
    def test_click_center_of_top_left_cell(self):
        self.assertEqual(screen_to_cell(50, 50, cell_size=100), (0, 0))

    def test_click_next_cell_to_the_right(self):
        self.assertEqual(screen_to_cell(150, 50, cell_size=100), (0, 1))

    def test_click_next_cell_down(self):
        self.assertEqual(screen_to_cell(50, 150, cell_size=100), (1, 0))

    def test_uses_default_cell_size_of_100(self):
        self.assertEqual(screen_to_cell(250, 350), (3, 2))


if __name__ == '__main__':
    unittest.main()
