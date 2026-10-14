"""Double-click (or `python run_library.py`) to open the vRigger object library."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vrigger_library.cli import main  # noqa: E402

sys.exit(main())
