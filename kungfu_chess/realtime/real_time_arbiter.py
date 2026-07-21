from ..constants import SHORT_REST_MS, LONG_REST_MS
from ..rules.algebraic import cell_to_algebraic

# Rest duration a piece takes after landing from each kind of action,
# matching the asset pack's jump -> short_rest / move -> long_rest graph.
_REST_DURATIONS = {
    'short_rest': SHORT_REST_MS,
    'long_rest': LONG_REST_MS,
}


class RealTimeArbiter:
    """Resolves queued moves and jumps against the current game clock.

    Moves and jumps travel over time instead of applying instantly; this
    class is where arrivals, blocked landings, captures, promotions,
    airborne (jump) collisions, and game-over are all decided.
    """

    def resolve(self, board, current_time_ms: int) -> None:
        if board._game_over:
            return

        self._resolve_moves(board, current_time_ms)

        if board._game_over:
            board._active_moves = []
            board._active_jumps = []
            return

        self._resolve_jumps(board, current_time_ms)

    def _resolve_moves(self, board, current_time_ms: int) -> None:
        board._active_moves.sort(key=lambda m: m.arrival_time)
        ready = [m for m in board._active_moves if current_time_ms >= m.arrival_time]
        remaining_moves = [m for m in board._active_moves if current_time_ms < m.arrival_time]

        # Group moves landing this tick by destination so two pieces truly
        # arriving at the same place at the same time are resolved as a
        # single event, rather than one-at-a-time in incidental queue order.
        by_destination = {}
        for move in ready:
            by_destination.setdefault((move.to_row, move.to_col), []).append(move)

        for moves_here in by_destination.values():
            colors = {m.piece_token[0] for m in moves_here}
            if len(moves_here) > 1 and len(colors) > 1:
                self._resolve_head_on_collision(board, moves_here)
            else:
                primary, *rest = moves_here
                self._resolve_single_move(board, primary, remaining_moves, current_time_ms)
                for move in rest:
                    # Same-color pieces racing for the same empty square:
                    # the first-queued one claims it, the rest try to
                    # return home like any other blocked move.
                    self._return_home(board, move, remaining_moves, current_time_ms)

            if board._game_over:
                break

        board._active_moves = remaining_moves

    def _resolve_single_move(self, board, move, remaining_moves, current_time_ms: int) -> None:
        airborne = self._find_airborne(board, move.to_row, move.to_col, move.arrival_time)
        if airborne is not None:
            if airborne.piece_token[0] == move.piece_token[0]:
                self._return_home(board, move, remaining_moves, current_time_ms)
            else:
                self._record_capture(board, airborne.piece_token, move.piece_token)
                self._record_log(
                    board,
                    f"{airborne.piece_token} holds "
                    f"{self._algebraic(board, airborne.row, airborne.col)} "
                    f"x{move.piece_token}"
                )
                board._grid[airborne.row][airborne.col] = airborne.piece_token
                board._active_jumps.remove(airborne)
                # The airborne piece just landed (by winning a fight), so it
                # rests exactly like any other jump landing.
                self._set_cooldown(board, airborne.row, airborne.col, current_time_ms, 'short_rest')
            return

        target_current = board._grid[move.to_row][move.to_col]
        if target_current != '.' and target_current[0] == move.piece_token[0]:
            self._return_home(board, move, remaining_moves, current_time_ms)
            return

        if target_current != '.' and target_current[1] == 'K':
            board._game_over = True
            board._winner = move.piece_token[0]  # 'w' or 'b' -- the color that captured the king

        board._grid[move.to_row][move.to_col] = self._final_token(board, move)
        self._set_cooldown(board, move.to_row, move.to_col, current_time_ms, 'long_rest')

        captured_token = target_current if target_current != '.' else None
        if captured_token is not None:
            self._record_capture(board, move.piece_token, captured_token)

        description = (
            f"{move.piece_token} "
            f"{self._algebraic(board, move.from_row, move.from_col)}-"
            f"{self._algebraic(board, move.to_row, move.to_col)}"
        )
        if captured_token is not None:
            description += f" x{captured_token}"
        self._record_log(board, description)

    def _return_home(self, board, move, remaining_moves, current_time_ms: int) -> None:
        """Send a blocked move's piece back to where it started.

        The origin cell is normally empty (it was vacated the instant the
        move was queued), but another piece can legally have moved into it
        in the meantime. A piece must never simply vanish, so: an enemy
        occupying the home cell is captured and the square reclaimed; a
        friendly occupant means home isn't free yet, so the move keeps
        waiting and retries on a later tick.
        """
        home_occupant = board._grid[move.from_row][move.from_col]
        if home_occupant == '.':
            board._grid[move.from_row][move.from_col] = move.piece_token
            return

        if home_occupant[0] != move.piece_token[0]:
            self._record_capture(board, move.piece_token, home_occupant)
            board._grid[move.from_row][move.from_col] = move.piece_token
            self._set_cooldown(board, move.from_row, move.from_col, current_time_ms, 'long_rest')
            self._record_log(
                board,
                f"{move.piece_token} holds "
                f"{self._algebraic(board, move.from_row, move.from_col)} "
                f"x{home_occupant}"
            )
            return

        remaining_moves.append(move)

    def _resolve_head_on_collision(self, board, moves) -> None:
        """Two or more opposing pieces arrive at the same cell at the same
        instant: none of them wins the square, all of them are destroyed."""
        for capturer in moves:
            for victim in moves:
                if victim is not capturer:
                    self._record_capture(board, capturer.piece_token, victim.piece_token)

        to_row, to_col = moves[0].to_row, moves[0].to_col
        if board._grid[to_row][to_col] == '.':
            tokens = ", ".join(m.piece_token for m in moves)
            self._record_log(
                board,
                f"collision at {self._algebraic(board, to_row, to_col)}: {tokens} all destroyed"
            )

    def _resolve_jumps(self, board, current_time_ms: int) -> None:
        remaining_jumps = []
        for jump in board._active_jumps:
            if current_time_ms < jump.end_time:
                remaining_jumps.append(jump)
                continue

            occupant = board._grid[jump.row][jump.col]
            if occupant == '.':
                board._grid[jump.row][jump.col] = jump.piece_token
                self._set_cooldown(board, jump.row, jump.col, current_time_ms, 'short_rest')
            elif occupant[0] != jump.piece_token[0]:
                self._record_capture(board, jump.piece_token, occupant)
                board._grid[jump.row][jump.col] = jump.piece_token
                self._set_cooldown(board, jump.row, jump.col, current_time_ms, 'short_rest')
                self._record_log(
                    board,
                    f"{jump.piece_token} holds "
                    f"{self._algebraic(board, jump.row, jump.col)} "
                    f"x{occupant}"
                )
            else:
                # Home is still held by a friendly piece; keep waiting to land.
                remaining_jumps.append(jump)

        board._active_jumps = remaining_jumps

    @staticmethod
    def _find_airborne(board, row: int, col: int, arrival_time: int):
        for jump in board._active_jumps:
            if jump.row == row and jump.col == col and jump.end_time >= arrival_time:
                return jump
        return None

    @staticmethod
    def _record_capture(board, capturing_token: str, captured_token: str) -> None:
        board._captured[capturing_token[0]].append(captured_token)

    @staticmethod
    def _record_log(board, description: str) -> None:
        board._move_log.append(description)

    @staticmethod
    def _set_cooldown(board, row: int, col: int, current_time_ms: int, state: str) -> None:
        board._cooldowns[(row, col)] = (current_time_ms + _REST_DURATIONS[state], state)

    @staticmethod
    def _algebraic(board, row: int, col: int) -> str:
        return cell_to_algebraic(row, col, board._rows)

    @staticmethod
    def _final_token(board, move) -> str:
        if move.piece_token[1] != 'P':
            return move.piece_token
        promotes = (move.piece_token[0] == 'w' and move.to_row == 0) or \
                   (move.piece_token[0] == 'b' and move.to_row == board._rows - 1)
        return move.piece_token[0] + 'Q' if promotes else move.piece_token
