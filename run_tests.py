import sys
import os
import unittest

# Ensure project root is on sys.path so package imports work
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

START_DIR = os.path.join(PROJECT_ROOT, 'tests')

loader = unittest.TestLoader()
suite = loader.discover(start_dir=START_DIR)

runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)

sys.exit(0 if result.wasSuccessful() else 1)
