import unittest

from server import elo


class EloTests(unittest.TestCase):
    def test_equal_ratings_white_win_gains_half_k(self):
        new_white, new_black = elo.compute_new_ratings(1200, 1200, 'w')

        self.assertEqual(new_white, 1216)
        self.assertEqual(new_black, 1184)

    def test_equal_ratings_black_win_gains_half_k(self):
        new_white, new_black = elo.compute_new_ratings(1200, 1200, 'b')

        self.assertEqual(new_white, 1184)
        self.assertEqual(new_black, 1216)

    def test_underdog_win_gains_close_to_full_k(self):
        new_white, new_black = elo.compute_new_ratings(1200, 1600, 'w')

        self.assertEqual(new_white, 1229)
        self.assertEqual(new_black, 1571)

    def test_favorite_win_gains_only_a_small_amount(self):
        new_white, new_black = elo.compute_new_ratings(1600, 1200, 'w')

        self.assertEqual(new_white, 1603)
        self.assertEqual(new_black, 1197)


if __name__ == '__main__':
    unittest.main()
