import sys
from ..models.board import Board
from ..constants import NEW_LINE

class BoardParserApp:
    def __init__(self, input_stream, output_stream):
        self.input_stream = input_stream
        self.output_stream = output_stream
        self._game_clock_ms = 0

    def run(self):
        input_data = self.input_stream.read()
        if not input_data.strip():
            return
            
        lines = input_data.splitlines()
        board_lines = []
        command_lines = []
        in_board_section = False
        
        for line in lines:
            cleaned = line.strip()
            if not cleaned:
                continue
            if cleaned.startswith("Board:"):
                in_board_section = True
                continue
            elif cleaned.startswith("Commands:"):
                in_board_section = False
                continue
                
            if in_board_section:
                board_lines.append(line)
            else:
                command_lines.append(cleaned)

        board = None
        if board_lines:
            board = Board.from_text_lines(board_lines)
            if not board:
                return

        for command in command_lines:
            parts = command.split()
            if not parts:
                continue
                
            cmd_type = parts[0]
            
            if cmd_type == "click" and len(parts) == 3:
                try:
                    x = int(parts[1])
                    y = int(parts[2])
                    if board:
                        board.handle_click(x, y, self._game_clock_ms)
                except ValueError:
                    pass
                    
            elif cmd_type == "jump" and len(parts) == 3:
                try:
                    x = int(parts[1])
                    y = int(parts[2])
                    if board:
                        board.handle_jump_command(x, y, self._game_clock_ms)
                except ValueError:
                    pass
                    
            elif cmd_type == "wait" and len(parts) == 2:
                try:
                    ms = int(parts[1])
                    self._game_clock_ms += ms
                except ValueError:
                    pass
                    
            elif command == "print board":
                if board:
                    self.output_stream.write(board.get_canonical_string(self._game_clock_ms) + NEW_LINE)


if __name__ == "__main__":
    app = BoardParserApp(sys.stdin, sys.stdout)
    app.run()
