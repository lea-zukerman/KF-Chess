from ..constants import NEW_LINE


def print_board(board, ms, output_stream):
    output_stream.write(board.get_canonical_string(ms) + NEW_LINE)


def print_move_log(board, output_stream):
    for entry in board.get_move_log():
        output_stream.write(entry + NEW_LINE)


def print_score(board, output_stream):
    score = board.get_score()
    output_stream.write(f"w:{score['w']} b:{score['b']}" + NEW_LINE)
