"""Graphical game application."""

import pathlib
import time
from typing import Optional, Tuple

# Try to import cv2, fall back to mock if not available
try:
    import cv2
except ImportError:
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))
    import mock_cv2 as cv2

from kungfu_chess.model.board import Board
from kungfu_chess.model.game_state import GameState
from kungfu_chess.view.game_renderer import GameRenderer
from kungfu_chess.constants import CELL_SIZE


class GameApp:
    """Main graphical game application."""
    
    def __init__(self, board_text: str, pieces_dir: str | pathlib.Path,
                 window_size: Tuple[int, int] = (800, 800),
                 white_name: str = "White", black_name: str = "Black",
                 observer: bool = False):
        """
        Initialize the game application.

        Parameters
        ----------
        board_text : str
            Text representation of the board
        pieces_dir : str | Path
            Path to the pieces directory
        window_size : Tuple[int, int]
            Window size (width, height)
        white_name : str
            Display name for the white player
        black_name : str
            Display name for the black player
        observer : bool
            If True, run as a read-only spectator: no mouse input and no
            pause/reset controls, only rendering of the live board state.
        """
        self.window_name = "Kung Fu Chess"
        self.window_size = window_size
        self.pieces_dir = pathlib.Path(pieces_dir)
        self.observer = observer

        # Parse board
        lines = board_text.strip().split('\n')
        self.board = Board.from_text_lines(lines)
        if not self.board:
            raise ValueError("Invalid board configuration")

        # Initialize game state
        self.game_state = GameState(white_name, black_name)

        # Initialize renderer
        self.renderer = GameRenderer(self.pieces_dir, board_size=window_size)
        
        # Game loop variables
        self.running = True
        self.paused = False
        self.frame_count = 0
        self.last_frame_time = time.time()
        self.delta_ms = 16  # ~60 FPS
    
    def _window_to_board_cell(self, x: int, y: int) -> Tuple[int, int]:
        """Convert window coordinates to board row/column."""
        # The displayed board is resized to `self.window_size` before showing,
        # so map clicks based on the actual window dimensions.
        board_w, board_h = self.window_size

        col = int(x * self.board._cols / board_w)
        row = int(y * self.board._rows / board_h)
        col = max(0, min(self.board._cols - 1, col))
        row = max(0, min(self.board._rows - 1, row))
        return row, col

    def handle_mouse_click(self, event, x, y, flags, param):
        """Handle mouse click events."""
        if event == cv2.EVENT_LBUTTONDOWN:
            row, col = self._window_to_board_cell(x, y)
            current_time = int(time.time() * 1000) % 1000000  # Prevent overflow
            print(f"[DEBUG] Mouse click at window ({x},{y}) -> cell ({row},{col}), turn={self.game_state.current_turn}")
            result = self.board.handle_click_at_cell(row, col, current_time, self.game_state.current_turn)
            print(f"[DEBUG] handle_click_at_cell returned {result}; selected={self.board._selected_cell}; valid_moves={self.board._valid_moves}")
            if result:
                self.game_state.switch_turn()

        elif event == cv2.EVENT_RBUTTONDOWN:
            row, col = self._window_to_board_cell(x, y)
            current_time = int(time.time() * 1000) % 1000000
            print(f"[DEBUG] Right click at window ({x},{y}) -> cell ({row},{col}), turn={self.game_state.current_turn}")
            result = self.board.handle_jump_at_cell(row, col, current_time, self.game_state.current_turn)
            print(f"[DEBUG] handle_jump_at_cell returned {result}")
            if result:
                self.game_state.switch_turn()
    
    def render_frame(self, current_time_ms: int = 0):
        """Render a game frame."""
        # Render board and pieces
        canvas = self.renderer.render_frame(self.board, self.delta_ms, current_time_ms)
        
        # Resize to window size
        if canvas.img is not None:
            resized = cv2.resize(canvas.img, self.window_size, interpolation=cv2.INTER_LINEAR)
            return resized
        
        return None
    
    def run(self):
        """Run the game loop."""
        # Create window
        cv2.namedWindow(self.window_name)
        if not self.observer:
            cv2.setMouseCallback(self.window_name, self.handle_mouse_click)

        print("Kung Fu Chess - Graphical Mode")
        if self.observer:
            print("Observer mode: spectating only, no input accepted")
            print("Press 'q' to quit")
        else:
            print("Left click: Move or select piece")
            print("Right click: Jump piece in place")
            print("Press 'q' to quit, 'p' to pause/resume")
        
        try:
            while self.running:
                # Calculate delta time
                current_time = time.time()
                self.delta_ms = int((current_time - self.last_frame_time) * 1000)
                self.last_frame_time = current_time
                self.delta_ms = min(self.delta_ms, 33)  # Cap at ~30ms for stability
                
                if not self.paused:
                    # Update game state
                    current_time_ms = int(time.time() * 1000) % 1000000
                    self.board.update_moves_by_time(current_time_ms)

                    # Render frame
                    frame = self.render_frame(current_time_ms)
                    
                    if frame is not None:
                        # Add UI overlays
                        self._draw_ui_overlays(frame)
                        
                        # Display frame
                        cv2.imshow(self.window_name, frame)
                    
                    self.frame_count += 1
                
                # Handle keyboard input
                key = cv2.waitKey(max(1, 16 - self.delta_ms)) & 0xFF
                
                if key == ord('q'):
                    self.running = False
                elif key == ord('p') and not self.observer:
                    self.paused = not self.paused
                    state = "PAUSED" if self.paused else "RESUMED"
                    print(f"Game {state}")
                elif key == ord('r') and not self.observer:
                    self.reset_game()
        
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            cv2.destroyAllWindows()
    
    def _draw_ui_overlays(self, frame):
        """Draw UI information on the frame."""
        # Add game status
        status_text = f"Turn: {self.game_state.current_player_name()}"
        cv2.putText(frame, status_text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX,
                   0.7, (0, 255, 255), 2)

        # Add player names
        names_text = f"{self.game_state.white_name} (W) vs {self.game_state.black_name} (B)"
        cv2.putText(frame, names_text, (10, self.window_size[1] - 15), cv2.FONT_HERSHEY_SIMPLEX,
                   0.6, (255, 255, 255), 2)

        # Add observer banner
        if self.observer:
            cv2.putText(frame, "OBSERVER", (self.window_size[0] - 150, self.window_size[1] - 15),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)

        # Add score (material value of captured pieces per side)
        score = self.board.get_score()
        score_text = f"Score  W:{score['w']}  B:{score['b']}"
        cv2.putText(frame, score_text, (10, 50), cv2.FONT_HERSHEY_SIMPLEX,
                   0.6, (255, 255, 0), 2)

        # Add last move from the log
        move_log = self.board.get_move_log()
        if move_log:
            last_move_text = f"Last: {move_log[-1]}"
            cv2.putText(frame, last_move_text, (10, 75), cv2.FONT_HERSHEY_SIMPLEX,
                       0.6, (200, 200, 200), 2)

        # Add game over status
        if self.board.is_game_over():
            game_over_text = "GAME OVER!"
            cv2.putText(frame, game_over_text, (self.window_size[0]//2 - 100, 50), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)
        
        # Add frame counter
        fps_text = f"FPS: {1000 // max(1, self.delta_ms)}"
        cv2.putText(frame, fps_text, (self.window_size[0] - 150, 25), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    
    def reset_game(self):
        """Reset the game."""
        print("Resetting game...")
        self.game_state = GameState(self.game_state.white_name, self.game_state.black_name)
        # Create new board - would need original board text
        self.frame_count = 0


def create_default_board_text() -> str:
    """Create default chess starting position."""
    return """bR bN bB bQ bK bB bN bR
bP bP bP bP bP bP bP bP
.  .  .  .  .  .  .  .
.  .  .  .  .  .  .  .
.  .  .  .  .  .  .  .
.  .  .  .  .  .  .  .
wP wP wP wP wP wP wP wP
wR wN wB wQ wK wB wN wR"""
