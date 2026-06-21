"""Import-tolerant edge-case runner for the loop benchmark.

Runs every test_*.py in this directory whose imports resolve (i.e. whose target
function the current task actually added) and skips the rest, so one shared
`.verify/` can hold the hidden checks for several tasks. Exits non-zero if any
check fails OR if nothing ran (a task that added nothing must not "pass").
"""

import importlib
import pathlib
import sys
import unittest

here = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(here.parent))  # repo root, for `import ledger`
sys.path.insert(0, str(here))

suite = unittest.TestSuite()
loader = unittest.TestLoader()
for f in sorted(here.glob("test_*.py")):
    try:
        mod = importlib.import_module(f.stem)
    except Exception:
        continue  # target function not implemented by this task; skip
    suite.addTests(loader.loadTestsFromModule(mod))

if suite.countTestCases() == 0:
    print("no checks ran")
    sys.exit(1)

result = unittest.TextTestRunner(verbosity=0).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
