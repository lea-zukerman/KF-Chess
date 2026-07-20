import sys
import pathlib
import argparse
from kungfu_chess.io.board_parser import BoardParserApp
from kungfu_chess.view.game_app import GameApp, create_default_board_text


def find_default_pieces_dir() -> pathlib.Path:
    """Find the default pieces directory in common locations."""
    base_dir = pathlib.Path(__file__).resolve().parent.parent.parent
    candidates = [
        base_dir / 'repo' / 'CTD26' / 'pieces2',
        base_dir / 'CTD26' / 'pieces2',
        pathlib.Path.home() / 'Desktop' / 'repo' / 'CTD26' / 'pieces2',
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def main():
    parser = argparse.ArgumentParser(description="Kung Fu Chess")
    parser.add_argument('--graphical', '-g', action='store_true', 
                       help='Run in graphical mode')
    parser.add_argument('--pieces-dir', '-p', type=str,
                       default=str(find_default_pieces_dir()),
                       help='Path to pieces directory')
    parser.add_argument('--script', '-s', type=str,
                       help='Path to script file to run')
    parser.add_argument('--white-name', type=str, default='White',
                       help='Display name for the white player')
    parser.add_argument('--black-name', type=str, default='Black',
                       help='Display name for the black player')
    parser.add_argument('--observer', action='store_true',
                       help='Run in observer/spectator mode (view only, no input)')
    args = parser.parse_args()

    if args.graphical:
        # Run in graphical mode
        try:
            board_text = create_default_board_text()
            app = GameApp(board_text, args.pieces_dir,
                         white_name=args.white_name, black_name=args.black_name,
                         observer=args.observer)
            app.run()
        except FileNotFoundError as e:
            print(f"Error: {e}")
            print(f"Please ensure pieces directory exists at: {args.pieces_dir}")
            sys.exit(1)
    else:
        # Run in text mode with script parser
        app = BoardParserApp(sys.stdin, sys.stdout)
        app.run()


if __name__ == '__main__':
    main()
