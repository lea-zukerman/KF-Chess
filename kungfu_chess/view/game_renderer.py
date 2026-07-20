"""Game renderer for displaying board and pieces."""

import pathlib
from typing import Dict, List, Optional, Tuple
from .img import Img
from .asset_manager import PieceAssetManager
from ..model.board import Board
from ..model.position import Position


class AnimationState:
    """Tracks animation state for a piece."""
    
    def __init__(self, state_name: str, sprites: List[Img], frame_duration_ms: int = 100,
                 is_looping: bool = True):
        """
        Initialize animation state.

        Parameters
        ----------
        state_name : str
            Name of the state (e.g., 'idle', 'move')
        sprites : List[Img]
            List of sprite images for the animation
        frame_duration_ms : int
            Duration each frame is shown (milliseconds), driven by the
            asset pack's own config.json rather than a hardcoded guess
        is_looping : bool
            Whether the animation repeats or holds its last frame, also
            driven by config.json instead of being guessed per state name
        """
        self.state_name = state_name
        self.sprites = sprites
        self.frame_duration_ms = frame_duration_ms
        self.current_frame = 0
        self.elapsed_ms = 0
        self.is_looping = is_looping
    
    def update(self, delta_ms: int) -> Img:
        """
        Update animation and return current frame.
        
        Parameters
        ----------
        delta_ms : int
            Time elapsed since last update (milliseconds)
        
        Returns
        -------
        Img
            Current frame sprite
        """
        self.elapsed_ms += delta_ms
        
        while self.elapsed_ms >= self.frame_duration_ms:
            self.elapsed_ms -= self.frame_duration_ms
            self.current_frame += 1
            
            if self.current_frame >= len(self.sprites):
                if self.is_looping:
                    self.current_frame = 0
                else:
                    self.current_frame = len(self.sprites) - 1
        
        return self.sprites[self.current_frame]
    
    def reset(self):
        """Reset animation to first frame."""
        self.current_frame = 0
        self.elapsed_ms = 0


class PieceRenderer:
    """Renders individual pieces on the board."""
    
    def __init__(self, asset_manager: PieceAssetManager, cell_size: int = 64):
        """
        Initialize piece renderer.
        
        Parameters
        ----------
        asset_manager : PieceAssetManager
            Asset manager for loading sprites
        cell_size : int
            Size of each board cell in pixels
        """
        self.asset_manager = asset_manager
        self.cell_size = cell_size
        self.piece_animations: Dict[Tuple[int, int], AnimationState] = {}
        self.cell_pieces: Dict[Tuple[int, int], Tuple[str, str]] = {}
        self._animation_states_cache: Dict[str, Dict[str, List[Img]]] = {}
    
    def get_animation_states(self, piece: str) -> Dict[str, List[Img]]:
        """Get or load animation states for a piece."""
        if piece not in self._animation_states_cache:
            self._animation_states_cache[piece] = self.asset_manager.get_all_states_for_piece(
                piece, size=(self.cell_size, self.cell_size)
            )
        return self._animation_states_cache[piece]
    
    def set_piece_state(self, row: int, col: int, piece: str, state: str):
        """Set animation state for a piece at a position."""
        animations = self.get_animation_states(piece)
        if state in animations:
            config = self.asset_manager.get_state_config(piece, state)
            fps = config['frames_per_sec']
            frame_duration_ms = int(1000 / fps) if fps > 0 else 100
            self.piece_animations[(row, col)] = AnimationState(
                state, animations[state],
                frame_duration_ms=frame_duration_ms,
                is_looping=config['is_loop'],
            )
    
    def update_piece_animation(self, row: int, col: int, delta_ms: int) -> Optional[Img]:
        """
        Update animation for a piece and get current sprite.
        
        Parameters
        ----------
        row : int
            Board row
        col : int
            Board column
        delta_ms : int
            Time elapsed since last update
        
        Returns
        -------
        Optional[Img]
            Current sprite or None if no animation
        """
        if (row, col) not in self.piece_animations:
            return None
        
        return self.piece_animations[(row, col)].update(delta_ms)
    
    def get_current_sprite(self, row: int, col: int) -> Optional[Img]:
        """Get current sprite for a piece without updating."""
        if (row, col) not in self.piece_animations:
            return None
        
        anim = self.piece_animations[(row, col)]
        return anim.sprites[anim.current_frame]
    
    def clear_animation(self, row: int, col: int):
        """Clear animation for a position."""
        if (row, col) in self.piece_animations:
            del self.piece_animations[(row, col)]
        self.cell_pieces.pop((row, col), None)

    def render_piece(self, row: int, col: int, piece: str, delta_ms: int,
                      state: str = 'idle') -> Optional[Img]:
        """Get the current sprite for whichever piece occupies a cell.

        A capture or promotion changes which piece occupies a cell without
        the cell itself changing, and a piece can also switch state in place
        (e.g. idle -> jump -> idle), so a cached animation is only reused
        when it still belongs to that same (piece, state) pair; otherwise
        it's restarted so a stale sprite can't keep playing in its place.
        """
        if self.cell_pieces.get((row, col)) != (piece, state):
            self.clear_animation(row, col)
            self.set_piece_state(row, col, piece, state)
            self.cell_pieces[(row, col)] = (piece, state)

        sprite = self.update_piece_animation(row, col, delta_ms)
        if sprite is None:
            self.set_piece_state(row, col, piece, state)
            sprite = self.get_current_sprite(row, col)
        return sprite


class GameRenderer:
    """Main game renderer."""
    
    def __init__(self, pieces_dir: str | pathlib.Path, board_size: Tuple[int, int] = (512, 512)):
        """
        Initialize game renderer.
        
        Parameters
        ----------
        pieces_dir : str | Path
            Path to pieces directory
        board_size : Tuple[int, int]
            Size of the board canvas (width, height)
        """
        self.asset_manager = PieceAssetManager(pieces_dir)
        self.board_size = board_size
        self.piece_renderer = PieceRenderer(self.asset_manager, cell_size=board_size[0] // 8)
        self.canvas: Optional[Img] = None
        self.board_image: Optional[Img] = None
        self._init_board()
    
    def _init_board(self):
        """Initialize board image."""
        # Load board and resize to canvas size
        self.board_image = self.asset_manager.get_board_image(size=self.board_size)
        if self.board_image and self.board_image.img is not None:
            actual_width = self.board_image.img.shape[1]
            self.piece_renderer.cell_size = actual_width // 8

    def _get_cell_size(self) -> int:
        """Return the current size of one board cell in pixels."""
        if self.board_image and self.board_image.img is not None:
            return self.board_image.img.shape[1] // 8
        return self.board_size[0] // 8

    def render_frame(self, board: Board, delta_ms: int = 16, current_time_ms: int = 0) -> Img:
        """
        Render a game frame.

        Parameters
        ----------
        board : Board
            The game board state
        delta_ms : int
            Time elapsed since last frame
        current_time_ms : int
            Absolute game clock, used to tell whether a piece is currently
            resting (short_rest/long_rest) after having just acted

        Returns
        -------
        Img
            The rendered frame
        """
        # Clone board image as canvas
        self.canvas = self.board_image.clone()

        # Draw pieces
        for row in range(board._rows):
            for col in range(board._cols):
                piece = board._grid[row][col]
                if piece != '.':
                    state = board.resting_state(row, col, current_time_ms) or 'idle'
                    self._render_piece(row, col, piece, delta_ms, state=state)

        # Airborne (jumping) pieces are cleared from the grid for the
        # duration of the jump, so they need to be drawn separately or
        # they'd simply vanish until they land.
        for jump in board._active_jumps:
            self._render_piece(jump.row, jump.col, jump.piece_token, delta_ms, state='jump')

        # Draw selected cell indicator if any
        if board._selected_cell:
            self._draw_selection_indicator(board._selected_cell)
        
        # Draw valid moves for the selected piece if any
        if board._valid_moves:
            self._draw_valid_moves(board._valid_moves, board._rows, board._cols)
        
        return self.canvas

    def _render_piece(self, row: int, col: int, piece: str, delta_ms: int, state: str = 'idle'):
        """Render a single piece at a board position."""
        sprite = self.piece_renderer.render_piece(row, col, piece, delta_ms, state=state)
        
        if sprite:
            # Calculate pixel position
            cell_size = self._get_cell_size()
            x = col * cell_size
            y = row * cell_size
            
            # Clamp sprite to the board canvas if the board image width is not exactly divisible
            w, h = sprite.get_size()
            canvas_w, canvas_h = self.canvas.get_size()
            x = min(x, max(canvas_w - w, 0))
            y = min(y, max(canvas_h - h, 0))
            
            # Draw sprite on canvas
            sprite.draw_on(self.canvas, x, y)
    
    def _draw_selection_indicator(self, selected_cell: Tuple[int, int]):
        """Draw an indicator for the selected cell."""
        row, col = selected_cell
        cell_size = self._get_cell_size()
        x = col * cell_size
        y = row * cell_size
        
        # Draw green rectangle around selected cell
        self.canvas.draw_rectangle(x, y, cell_size, cell_size, 
                                   color=(0, 255, 0, 255), thickness=3)
    
    def _draw_valid_moves(self, moves: List[Tuple[int, int, int, int]], 
                          rows: int, cols: int):
        """Draw indicators for valid move destinations."""
        cell_size = self._get_cell_size()
        
        for move in moves:
            from_row, from_col, to_row, to_col = move[:4]
            x = to_col * cell_size + cell_size // 2
            y = to_row * cell_size + cell_size // 2
            
            # Draw cyan circle at destination
            self.canvas.draw_circle(x, y, cell_size // 6, 
                                   color=(255, 255, 0, 255), thickness=2)
    
    def show_frame(self):
        """Display the current frame."""
        if self.canvas:
            self.canvas.show()
    
    def save_frame(self, path: str):
        """Save the current frame to a file."""
        if self.canvas:
            self.canvas.save(path)
