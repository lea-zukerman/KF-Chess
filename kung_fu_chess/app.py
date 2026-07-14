import sys
from kung_fu_chess.io.board_parser import BoardParserApp


def main():
    app = BoardParserApp(sys.stdin, sys.stdout)
    app.run()


if __name__ == '__main__':
    main()
