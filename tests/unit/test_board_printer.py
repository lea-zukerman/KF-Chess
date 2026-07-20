import io
import unittest

from kungfu_chess.io.board_printer import print_board
from kungfu_chess.model.board import Board


class BoardPrinterTests(unittest.TestCase):
    def test_print_board_output(self):
        board = Board.from_text_lines(['. .', 'wP .'])
        output_stream = io.StringIO()

        print_board(board, 0, output_stream)
        self.assertEqual(output_stream.getvalue(), '. .\nwP .\n')


if __name__ == '__main__':
    unittest.main()
