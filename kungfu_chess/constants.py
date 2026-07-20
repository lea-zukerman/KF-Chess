# Common game configuration values and token definitions

NEW_LINE = "\n"
CELL_SIZE = 100
MS_PER_CELL = 1000
JUMP_DURATION_MS = 1000
# Cooldown a piece rests for after landing, matching the asset pack's
# jump -> short_rest / move -> long_rest state graph. The pack's config.json
# files specify animation frame rates and loop behavior for these states but
# no numeric duration, so these are this game's own rule, not derived data.
SHORT_REST_MS = 500
LONG_REST_MS = 1000
VALID_PIECES = {'K', 'Q', 'R', 'B', 'N', 'P'}
PIECE_COLORS = {'w', 'b'}
PIECE_NAMES = {
    'K': 'king',
    'Q': 'queen',
    'R': 'rook',
    'B': 'bishop',
    'N': 'knight',
    'P': 'pawn',
}
PIECE_VALUES = {
    'K': 0,
    'Q': 9,
    'R': 5,
    'B': 3,
    'N': 3,
    'P': 1,
}
