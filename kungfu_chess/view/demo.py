"""Demo of the graphics rendering system."""

import pathlib
import sys
from typing import Tuple

# Add parent directory to path
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

from kungfu_chess.model.board import Board
from kungfu_chess.model.game_state import GameState
from kungfu_chess.view.game_renderer import GameRenderer
from kungfu_chess.view.game_app import GameApp, create_default_board_text


def demo_static_render():
    """Render a static demo board."""
    pieces_dir = pathlib.Path(r"c:\Users\USER\Desktop\repo\CTD26\pieces2")
    
    if not pieces_dir.exists():
        print(f"Error: Pieces directory not found at {pieces_dir}")
        print("Please ensure CTD26 is extracted to c:\\Users\\USER\\Desktop\\repo\\")
        return
    
    # Initialize renderer
    print("Initializing renderer...")
    renderer = GameRenderer(pieces_dir, board_size=(512, 512))
    
    # Create demo board with pieces in various positions
    grid = [
        ['br', 'bn', 'bb', 'bq', 'bk', 'bb', 'bn', 'br'],
        ['bp', 'bp', 'bp', 'bp', 'bp', 'bp', 'bp', 'bp'],
        ['.', '.', '.', '.', '.', '.', '.', '.'],
        ['.', '.', '.', '.', '.', '.', '.', '.'],
        ['.', '.', '.', '.', '.', '.', '.', '.'],
        ['.', '.', '.', '.', '.', '.', '.', '.'],
        ['wp', 'wp', 'wp', 'wp', 'wp', 'wp', 'wp', 'wp'],
        ['wr', 'wn', 'wb', 'wq', 'wk', 'wb', 'wn', 'wr'],
    ]
    board = Board(grid)
    
    # Render and display
    print("Rendering frame...")
    frame = renderer.render_frame(board, delta_ms=16)
    
    # Save for inspection
    output_path = pathlib.Path(__file__).parent.parent.parent / "demo_output.png"
    print(f"Saving to {output_path}...")
    renderer.save_frame(str(output_path))
    
    print("Demo complete! Output saved.")


def demo_interactive():
    """Run interactive graphical demo."""
    pieces_dir = pathlib.Path(r"c:\Users\USER\Desktop\repo\CTD26\pieces2")
    
    if not pieces_dir.exists():
        print(f"Error: Pieces directory not found at {pieces_dir}")
        print("Please ensure CTD26 is extracted to c:\\Users\\USER\\Desktop\\repo\\")
        return
    
    print("Starting interactive game...")
    board_text = create_default_board_text()
    app = GameApp(board_text, pieces_dir, window_size=(800, 800))
    app.run()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Kung Fu Chess Demo")
    parser.add_argument('--static', '-s', action='store_true',
                       help='Run static render demo (saves image)')
    parser.add_argument('--interactive', '-i', action='store_true',
                       help='Run interactive game demo')
    args = parser.parse_args()
    
    if args.static:
        demo_static_render()
    elif args.interactive:
        demo_interactive()
    else:
        print("Demo modes:")
        print("  --static       : Render static board and save as image")
        print("  --interactive  : Run interactive graphical game")
        print("\nRunning static demo...")
        demo_static_render()
