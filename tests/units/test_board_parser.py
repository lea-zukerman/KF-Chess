import io
import unittest

from kung_fu_chess.io.board_parser import BoardParserApp


class BoardParserTests(unittest.TestCase):
    def test_click_and_print_board(self):
        input_text = (
            'Board:\n'
            '. .\n'
            'wP .\n'
            'Commands:\n'
            'click 0 100\n'
            'click 0 0\n'
            'wait 1000\n'
            'print board\n'
        )
        output_stream = io.StringIO()
        app = BoardParserApp(io.StringIO(input_text), output_stream)
        app.run()

        self.assertEqual(output_stream.getvalue(), 'wQ .\n. .\n')


if __name__ == '__main__':
    unittest.main()
