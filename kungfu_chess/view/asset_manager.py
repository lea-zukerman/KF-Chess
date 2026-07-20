"""Asset manager for piece sprites and animations."""

import json
import pathlib
from typing import Dict, List, Optional, Tuple
from .img import Img

DEFAULT_STATE_CONFIG = {
    'frames_per_sec': 10,
    'is_loop': True,
    'speed_m_per_sec': 0.0,
    'next_state_when_finished': 'idle',
}


class PieceAssetManager:
    """Manages loading and caching of piece sprites and animations."""

    # Piece color mappings
    PIECE_COLORS = {'w': 'W', 'b': 'B'}  # 'w' -> 'W', 'b' -> 'B'
    PIECE_TYPES = {'p': 'P', 'r': 'R', 'n': 'N', 'b': 'B', 'q': 'Q', 'k': 'K'}
    
    # Animation states
    STATES = ['idle', 'move', 'jump', 'short_rest', 'long_rest']

    def __init__(self, pieces_dir: str | pathlib.Path):
        """
        Initialize the asset manager.
        
        Parameters
        ----------
        pieces_dir : str | Path
            Path to the pieces directory (e.g., CTD26/pieces2)
        """
        self.pieces_dir = pathlib.Path(pieces_dir)
        self._sprite_cache: Dict[str, Dict[str, List[Img]]] = {}
        self._config_cache: Dict[str, dict] = {}
        self._board_img: Optional[Img] = None

    def get_piece_key(self, piece: str) -> str:
        """
        Get the key for a piece (e.g., 'wp' or 'wP' -> 'PW').
        
        Parameters
        ----------
        piece : str
            Two-character piece string, e.g., 'wp' or 'wP' (white pawn)
            Format: [color][type] where color in 'wb' and type in 'prnbqk' or 'PRNBQK'
        
        Returns
        -------
        str
            Key like 'PW', 'KB', etc.
        """
        if len(piece) != 2:
            return None
        color = piece[0].lower()
        piece_type = piece[1].lower()
        
        if color not in self.PIECE_COLORS or piece_type not in self.PIECE_TYPES:
            return None
        
        return self.PIECE_TYPES[piece_type] + self.PIECE_COLORS[color]

    def get_board_image(self, size: Tuple[int, int] | None = None) -> Img:
        """Load the board image."""
        board_path = self.pieces_dir.parent / 'board.png'
        if not board_path.exists():
            raise FileNotFoundError(f"Board image not found: {board_path}")
        
        board = Img().read(str(board_path), size=size, keep_aspect=False)
        return board

    def get_state_config(self, piece: str, state: str) -> dict:
        """
        Load the physics/graphics config for a piece's animation state.

        Falls back to DEFAULT_STATE_CONFIG for anything missing from the
        state's config.json (or if the file doesn't exist at all), so
        callers never have to special-case a missing config.

        Parameters
        ----------
        piece : str
            Two-character piece string (e.g., 'wp', 'bk')
        state : str
            Animation state (e.g., 'idle', 'move', 'jump')

        Returns
        -------
        dict
            Keys: frames_per_sec, is_loop, speed_m_per_sec, next_state_when_finished
        """
        piece_key = self.get_piece_key(piece)
        if not piece_key:
            raise ValueError(f"Invalid piece: {piece}")

        cache_key = f"{piece_key}_{state}"
        if cache_key in self._config_cache:
            return self._config_cache[cache_key]

        config = dict(DEFAULT_STATE_CONFIG)
        config_path = self.pieces_dir / piece_key / 'states' / state / 'config.json'
        if config_path.exists():
            with open(config_path, encoding='utf-8') as f:
                raw = json.load(f)
            config['frames_per_sec'] = raw.get('graphics', {}).get('frames_per_sec', config['frames_per_sec'])
            config['is_loop'] = raw.get('graphics', {}).get('is_loop', config['is_loop'])
            config['speed_m_per_sec'] = raw.get('physics', {}).get('speed_m_per_sec', config['speed_m_per_sec'])
            config['next_state_when_finished'] = raw.get('physics', {}).get(
                'next_state_when_finished', config['next_state_when_finished']
            )

        self._config_cache[cache_key] = config
        return config

    def load_sprite(self, piece: str, state: str, sprite_num: int) -> Img:
        """
        Load a single sprite for a piece in a specific state.
        
        Parameters
        ----------
        piece : str
            Two-character piece string (e.g., 'wp', 'bk')
        state : str
            Animation state (e.g., 'idle', 'move', 'jump')
        sprite_num : int
            Sprite number in the sequence
        
        Returns
        -------
        Img
            The loaded sprite image
        """
        piece_key = self.get_piece_key(piece)
        if not piece_key:
            raise ValueError(f"Invalid piece: {piece}")
        
        if state not in self.STATES:
            raise ValueError(f"Invalid state: {state}. Must be one of {self.STATES}")
        
        # Build path: pieces_dir/PW/states/idle/sprites/1.png
        sprite_path = (self.pieces_dir / piece_key / 'states' / state / 'sprites' / f'{sprite_num}.png')
        
        if not sprite_path.exists():
            raise FileNotFoundError(f"Sprite not found: {sprite_path}")
        
        return Img().read(str(sprite_path), keep_aspect=True)

    def load_animation(self, piece: str, state: str, size: Tuple[int, int] | None = None) -> List[Img]:
        """
        Load all sprites for a piece in a specific state.
        
        Parameters
        ----------
        piece : str
            Two-character piece string (e.g., 'wp', 'bk')
        state : str
            Animation state (e.g., 'idle', 'move', 'jump')
        size : Tuple[int, int] | None
            Target size for each sprite (width, height)
        
        Returns
        -------
        List[Img]
            List of sprites for the animation
        """
        piece_key = self.get_piece_key(piece)
        if not piece_key:
            raise ValueError(f"Invalid piece: {piece}")
        
        if state not in self.STATES:
            raise ValueError(f"Invalid state: {state}. Must be one of {self.STATES}")
        
        cache_key = f"{piece_key}_{state}"
        if cache_key in self._sprite_cache:
            return self._sprite_cache[cache_key]
        
        sprites_dir = self.pieces_dir / piece_key / 'states' / state / 'sprites'
        if not sprites_dir.exists():
            raise FileNotFoundError(f"Sprites directory not found: {sprites_dir}")
        
        # Find all .png files and sort by number
        png_files = sorted([f for f in sprites_dir.iterdir() if f.suffix.lower() == '.png'],
                          key=lambda x: int(x.stem))
        
        if not png_files:
            raise FileNotFoundError(f"No sprites found in {sprites_dir}")
        
        sprites = []
        for png_file in png_files:
            sprite = Img().read(str(png_file), size=size, keep_aspect=True)
            sprites.append(sprite)
        
        self._sprite_cache[cache_key] = sprites
        return sprites

    def get_all_states_for_piece(self, piece: str, size: Tuple[int, int] | None = None) -> Dict[str, List[Img]]:
        """
        Load all animation states for a piece.
        
        Parameters
        ----------
        piece : str
            Two-character piece string (e.g., 'wp', 'bk')
        size : Tuple[int, int] | None
            Target size for each sprite
        
        Returns
        -------
        Dict[str, List[Img]]
            Dictionary mapping state names to sprite lists
        """
        states_dict = {}
        for state in self.STATES:
            try:
                states_dict[state] = self.load_animation(piece, state, size=size)
            except FileNotFoundError:
                # Some states might not exist for all pieces
                pass
        
        return states_dict

    def clear_cache(self):
        """Clear the sprite and config caches to free memory."""
        self._sprite_cache.clear()
        self._config_cache.clear()
