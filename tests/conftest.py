"""Make the test suite test THIS checkout, not whatever is pip-installed.

This is a src-layout package, so `import census_loader` normally resolves to
the installed distribution. If an editable install points somewhere else (a
second clone, a scratch directory), the suite silently tests that other tree
instead, and a green run says nothing about the code you are looking at.

Measured 2026-08-28: that was the live situation here. The editable install
resolved to a different clone entirely, so pytest in this repository was
exercising another repository's source.

Putting this repo's `src/` at the front of sys.path makes the suite honest,
and costs nothing when the install already points here.
"""

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if _SRC.is_dir():
    sys.path.insert(0, str(_SRC))
