from ..constants import NEW_LINE


def print_board(board, ms, output_stream):
    output_stream.write(board.get_canonical_string(ms) + NEW_LINE)
