import os
import runpy
import sys
from pathlib import Path

deps_dir = Path(__file__).parent / "deps"
if not deps_dir.exists():
    deps_dir.mkdir()

setup_dir = Path(__file__).parent.parent

if not (deps_dir / "venvstarter.py").exists():
    os.system(f"{sys.executable} -m pip install {setup_dir} -t {deps_dir}")

manager = runpy.run_path(str(deps_dir / "venvstarter.py"))["manager"]
