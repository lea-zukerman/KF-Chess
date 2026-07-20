import io
import os
import unittest

from kungfu_chess.io.board_parser import BoardParserApp


class IntegrationScriptTests(unittest.TestCase):
    def run_script(self, script_path):
        with open(script_path, 'r', encoding='utf-8') as f:
            content = f.read()

        input_data = content
        output_stream = io.StringIO()
        app = BoardParserApp(io.StringIO(input_data), output_stream)
        app.run()
        return output_stream.getvalue()

    def test_01_board_parsing(self):
        result = self.run_script(os.path.join('tests', 'integration', 'scripts', '01_board_parsing.kfc'))
        self.assertEqual(result, '. . .\nwP . .\n. . bK\n')

    def test_02_click_to_move(self):
        result = self.run_script(os.path.join('tests', 'integration', 'scripts', '02_click_to_move.kfc'))
        self.assertEqual(result, 'wK . .\n. . .\n. . bK\n')

    def test_03_rook_moves(self):
        result = self.run_script(os.path.join('tests', 'integration', 'scripts', '03_rook_moves.kfc'))
        self.assertEqual(result, 'wR . .\n. . .\n. . .\n')

    def test_04_invalid_moves(self):
        result = self.run_script(os.path.join('tests', 'integration', 'scripts', '04_invalid_moves.kfc'))
        self.assertEqual(result, '. . .\nwK . .\n. . .\n')

    def test_05_capture(self):
        result = self.run_script(os.path.join('tests', 'integration', 'scripts', '05_capture.kfc'))
        self.assertEqual(result, '. . .\n. . .\n. wQ .\n')

    def test_06_game_over(self):
        result = self.run_script(os.path.join('tests', 'integration', 'scripts', '06_game_over.kfc'))
        self.assertEqual(result, '. . .\n. . .\n. . wQ\n')


if __name__ == '__main__':
    unittest.main()
