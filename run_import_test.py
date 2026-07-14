import importlib

packages = [
    'kung_fu_chess',
    'kung_fu_chess.models',
    'kung_fu_chess.io',
]

for p in packages:
    try:
        importlib.import_module(p)
        print('OK', p)
    except Exception as e:
        print('FAIL', p, e)
