"""Standard ELO rating math -- pure functions, no DB or network dependency."""

K_FACTOR = 32


def expected_score(own_elo: int, opponent_elo: int) -> float:
    return 1 / (1 + 10 ** ((opponent_elo - own_elo) / 400))


def compute_new_ratings(white_elo: int, black_elo: int, winner: str) -> tuple[int, int]:
    """winner is 'w' or 'b'. Returns (new_white_elo, new_black_elo)."""
    score_w = 1 if winner == 'w' else 0
    score_b = 1 - score_w

    new_white = round(white_elo + K_FACTOR * (score_w - expected_score(white_elo, black_elo)))
    new_black = round(black_elo + K_FACTOR * (score_b - expected_score(black_elo, white_elo)))
    return new_white, new_black
