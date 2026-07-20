def screen_to_cell(x, y, cell_size=100):
    col = x // cell_size
    row = y // cell_size
    return int(row), int(col)
