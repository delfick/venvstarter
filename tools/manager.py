import os
import typing as tp
from pathlib import Path

from venvstarter.manager import manager

here = Path(__file__).parent


def run(venv_location: Path, args: tp.List[str]) -> tp.Union[None, str, tp.List[str]]:
    devtools_location = Path(__file__).parent / "devtools.py"
    return ["python", str(devtools_location)]


manager = manager(run).named(".python")

manager.add_local_dep(
    "{here}",
    "..",
    version_file=("venvstarter.py",),
    name="venvstarter=={version}",
    with_tests=True,
)

if "TOX_PYTHON" in os.environ:
    folder = Path(os.environ["TOX_PYTHON"]).parent.parent
    manager.place_venv_in(folder.parent)
    manager.named(folder.name)
else:
    manager.add_requirements_file("{here}", "requirements.dev.txt")
    manager.add_requirements_file("{here}", "requirements.docs.txt")

manager.run()
