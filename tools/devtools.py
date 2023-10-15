import inspect
import os
import platform
import shlex
import shutil
import sys
import typing as tp
from pathlib import Path

here = Path(__file__).parent

if platform.system() == "Windows":
    import mslex

    shlex = mslex  # noqa

if sys.version_info < (3, 10):
    Dict = tp.Dict
    List = tp.List
else:
    Dict = dict
    List = list


class Command(tp.Protocol):
    __is_command__: bool

    def __call__(self, bin_dir: Path, args: List[str]) -> None:
        ...


def command(func: tp.Callable) -> tp.Callable:
    tp.cast(Command, func).__is_command__ = True
    return func


def run(*args: tp.Union[str, Path], _env: tp.Union[None, Dict[str, str]] = None) -> None:
    cmd = " ".join(shlex.quote(str(part)) for part in args)
    print(f"Running '{cmd}'")
    ret = os.system(cmd)
    if ret != 0:
        sys.exit(1)


class App:
    commands: Dict[str, Command]

    def __init__(self):
        self.commands = {}

        compare = inspect.signature(type("C", (Command,), {})().__call__)

        for name in dir(self):
            val = getattr(self, name)
            if getattr(val, "__is_command__", False):
                assert (
                    inspect.signature(val) == compare
                ), f"Expected '{name}' to have correct signature, have {inspect.signature(val)} instead of {compare}"
                self.commands[name] = val

    def __call__(self, args: List[str]) -> None:
        bin_dir = Path(sys.executable).parent

        if args and args[0] in self.commands:
            os.chdir(here.parent)
            self.commands[args[0]](bin_dir, args[1:])
            return

        sys.exit(f"Unknown command:\nAvailable: {sorted(self.commands)}\nWanted: {args}")

    @command
    def format(self, bin_dir: Path, args: List[str]) -> None:
        if not args:
            args = [".", *args]
        run(bin_dir / "black", *args)
        run(bin_dir / "isort", *args)

    @command
    def lint(self, bin_dir: Path, args: List[str]) -> None:
        run(bin_dir / "pylama", *args)

    @command
    def tests(self, bin_dir: Path, args: List[str]) -> None:
        if "-q" not in args:
            args = ["-q", *args]
        run(bin_dir / "pytest", *args, _env={"NOSE_OF_YETI_BLACK_COMPAT": "false"})

    @command
    def tox(self, bin_dir: Path, args: List[str]) -> None:
        run(bin_dir / "tox", *args)

    @command
    def types(self, bin_dir: Path, args: List[str]) -> None:
        if args and args[0] == "restart":
            args.pop(0)
            run(bin_dir / "dmypy", "stop")

        args: List[tp.Union[str, Path]] = ["run", *args]
        if "--" not in args:
            args.extend(["--", "."])

        if "--show-column-numbers" not in args:
            args.append("--show-column-numbers")

        if "--config" not in args:
            args.append("--config-file")
            args.append(Path("pyproject.toml").absolute())

        run(bin_dir / "dmypy", *args)

    @command
    def docs(self, bin_dir: Path, args: List[str]) -> None:
        docs_path = here / ".." / "docs"
        build_path = docs_path / "_build"
        command: List[tp.Union[Path, str]] = [bin_dir / "sphinx-build"]

        other_args: List[str] = []
        for arg in args:
            if arg == "fresh":
                if build_path.exists():
                    shutil.rmtree(build_path)
            elif arg == "view":
                command = [bin_dir / "sphinx-autobuild", "--port", "9876"]
            else:
                other_args.append(arg)

        os.chdir(docs_path)

        run(*command, ".", "_build/html", "-b", "html", "-d", "_build/doctrees", *other_args)


app = App()

if __name__ == "__main__":
    app(sys.argv[1:])
