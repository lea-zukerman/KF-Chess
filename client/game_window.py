"""Networked GUI presentation + input for one game.

The client is a "dumb terminal": the server is the sole authority. This
window renders whatever board the server last broadcast (rebuilt from the
StateUpdate text) and turns mouse clicks into MoveCommand/JumpCommand intents
queued for the network layer to send. It runs no game logic itself.

Rendering reuses kungfu_chess/view's GameRenderer; pixel->cell reuses
input/board_mapper; cell->algebraic reuses rules/algebraic. Only show()/open()
touch the actual cv2 display -- the state and input logic is display-free so
it can be tested headless.
"""

from __future__ import annotations

import asyncio
import pathlib

# Real cv2 when available, mock otherwise (matches kungfu_chess/view/game_app).
try:
    import cv2
except ImportError:  # pragma: no cover - exercised only without OpenCV
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
    import mock_cv2 as cv2

from kungfu_chess.input.board_mapper import screen_to_cell
from kungfu_chess.model.board import Board
from kungfu_chess.rules.algebraic import cell_to_algebraic
from kungfu_chess.view.game_renderer import GameRenderer

from protocol.messages import JumpCommand, MoveCommand, StateUpdate


class GameWindow:
    """Holds the latest server state, renders it, and emits click intents."""

    def __init__(self, pieces_dir: str | pathlib.Path, my_role: str,
                 board_size: tuple[int, int] = (512, 512)):
        self.window_name = "Kung Fu Chess"
        self.my_role = my_role  # 'w' / 'b' / 'observer'
        self.board_size = board_size
        self.renderer = GameRenderer(pieces_dir, board_size=board_size)

        self.board: Board | None = None       # display-only, rebuilt per StateUpdate
        self.state: StateUpdate | None = None  # latest overlay fields
        self.selected: tuple[int, int] | None = None  # source cell of a pending move
        self.status = ""                        # transient note (rejection / countdown)
        self.outgoing: asyncio.Queue = asyncio.Queue()
        self.running = True

    # ---- state from the server ----

    def apply_state(self, state: StateUpdate) -> None:
        """Rebuild the display board from the server's text snapshot."""
        self.board = Board.from_text_lines(state.board.split("\n"))
        if self.selected is not None:
            self.board._selected_cell = self.selected
        self.state = state

    def set_status(self, text: str) -> None:
        self.status = text

    # ---- input -> outgoing intents ----

    def on_mouse(self, event, x, y, flags=0, param=None) -> None:
        """cv2 mouse callback. Observers and pre-first-state clicks are ignored."""
        if self.my_role == "observer" or self.board is None:
            return
        row, col = screen_to_cell(x, y, self._cell_size())
        if not self._in_bounds(row, col):
            return
        if event == cv2.EVENT_LBUTTONDOWN:
            self._left_click(row, col)
        elif event == cv2.EVENT_RBUTTONDOWN:
            self._enqueue(JumpCommand(cell_to_algebraic(row, col, self.board._rows)))

    def _left_click(self, row: int, col: int) -> None:
        """First click selects a source cell; second click sends the move."""
        if self.selected is None:
            self.selected = (row, col)
            self.board._selected_cell = (row, col)
            return
        from_square = cell_to_algebraic(self.selected[0], self.selected[1], self.board._rows)
        to_square = cell_to_algebraic(row, col, self.board._rows)
        self._enqueue(MoveCommand(from_square, to_square))
        self.selected = None
        self.board._selected_cell = None

    def _enqueue(self, command: object) -> None:
        self.outgoing.put_nowait(command)

    def _cell_size(self) -> int:
        return self.board_size[0] // 8

    def _in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.board._rows and 0 <= col < self.board._cols

    # ---- rendering ----

    def render(self, delta_ms: int = 16, now_ms: int = 0):
        """Draw the current board + overlays and return the frame (numpy image),
        or None if no state has arrived yet."""
        if self.board is None:
            return None
        canvas = self.renderer.render_frame(self.board, delta_ms, now_ms)
        frame = canvas.img
        if frame is not None:
            self._draw_overlays(frame)
        return frame

    def _draw_overlays(self, frame) -> None:
        state = self.state
        if state is None:
            return
        font = cv2.FONT_HERSHEY_SIMPLEX

        def put(text, y, color):
            cv2.putText(frame, text, (10, y), font, 0.6, color, 2)

        put(f"Turn: {state.turn}", 25, (0, 255, 255))
        put(f"Score  W:{state.score_w}  B:{state.score_b}", 50, (255, 255, 0))
        put(f"You: {self.my_role}", 75, (0, 200, 0))
        if self.status:
            put(self.status, 100, (0, 165, 255))
        names = f"{state.white_name}(W,{state.white_elo}) vs {state.black_name}(B,{state.black_elo})"
        cv2.putText(frame, names, (10, frame.shape[0] - 15), font, 0.55, (255, 255, 255), 2)
        if state.game_over:
            won = f" - winner: {state.winner}" if state.winner else ""
            cv2.putText(frame, "GAME OVER" + won, (self.board_size[0] // 2 - 140, 40),
                        font, 1.0, (0, 0, 255), 3)

    # ---- cv2 display (needs a real screen; not unit-tested) ----

    def open(self) -> None:
        cv2.namedWindow(self.window_name)
        if self.my_role != "observer":
            cv2.setMouseCallback(self.window_name, self.on_mouse)

    def show(self, frame) -> int:
        if frame is not None:
            cv2.imshow(self.window_name, frame)
        return cv2.waitKey(1) & 0xFF

    def close(self) -> None:
        cv2.destroyAllWindows()
