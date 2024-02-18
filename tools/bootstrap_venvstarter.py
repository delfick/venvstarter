import sys
from pathlib import Path

setup_dir = Path(__file__).parent.parent

if not any(Path(path).absolute() == setup_dir.absolute() for path in sys.path):
    sys.path.append(str(setup_dir))

from venvstarter import manager  # noqa:E402

__all__ = ["manager"]
