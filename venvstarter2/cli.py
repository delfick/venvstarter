import argparse
import os
import pathlib
import subprocess
import sys
import textwrap
from collections.abc import Iterator
from typing import TYPE_CHECKING, Protocol, TypeVar

if TYPE_CHECKING:
    from typing_extensions import Self

T_Command = TypeVar("T_Command", bound="CommandProtocol")


class CommandProtocol(Protocol):
    __name__: str

    def __call__(self, *, command: "Command", args: list[str]) -> None: ...


class Register:
    def __init__(self) -> None:
        self._commands: dict[str, CommandProtocol] = {}

    def command(self, func: T_Command) -> T_Command:
        if func.__name__ in self._commands:
            raise ValueError(f"Already have a command '{func.__name__}' registered")

        self._commands[func.__name__] = func
        return func

    def __contains__(self, name: str) -> bool:
        return name in self._commands

    def __iter__(self) -> Iterator[tuple[str, CommandProtocol]]:
        yield from self._commands.items()

    def __getitem__(self, name: str) -> CommandProtocol:
        return self._commands[name]


class Command:
    @classmethod
    def from_cli(cls, register: Register, argv: list[str] | None = None) -> "Self":
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--venvstarter-project-root",
            default=(
                None
                if (key := "VENVSTARTER_PROJECT_ROOT") not in os.environ
                else pathlib.Path(os.environ[key])
            ),
            type=pathlib.Path,
            required=key not in os.environ,
        )
        parser.add_argument(
            "--venvstarter-uv",
            default=(
                None
                if (key := "VENVSTARTER_UV") not in os.environ
                else pathlib.Path(os.environ[key])
            ),
            type=pathlib.Path,
            required=key not in os.environ,
        )
        parser.add_argument(
            "--venvstarter-python-path",
            default=pathlib.Path(sys.executable),
            type=pathlib.Path,
        )
        args, _ = parser.parse_known_args(
            [a for a in (argv or sys.argv[1:]) if a not in ("-h", "--help")]
        )
        return cls(
            register=register,
            project_root=args.venvstarter_project_root,
            uv=args.venvstarter_uv,
            python_path=args.venvstarter_python_path,
        )

    def __init__(
        self,
        *,
        register: Register,
        project_root: pathlib.Path,
        uv: pathlib.Path,
        python_path: pathlib.Path,
    ) -> None:
        self.project_root = project_root
        self.register = register
        self.uv = uv
        self.python_path = python_path
        self.bin_dir = self.python_path.parent

    def path_for(self, name: str) -> str:
        location = self.bin_dir / name
        if not location.exists():
            if os.name == "nt":
                location = location.with_suffix(".exe")
            if not location.exists():
                raise sys.exit(f"!!! No executable found: {location}")
        return str(location)

    def run_pip(self, *args: str) -> None:
        subprocess.run(
            [
                str(self.uv),
                "pip",
                "install",
                "-e",
                str(self.project_root),
                "-p",
                str(self.python_path),
            ],
            cwd=str(self.project_root),
            check=True,
        )

    def run(self, args: list[str] | None = None) -> None:
        if args is None:
            args = sys.argv[1:]

        if len(args) == 0 or args[0] not in self.register:
            lines: list[str] = [f"{sys.argv[0]} <task> ...args"]
            for name, command in sorted(self.register):
                description = (
                    textwrap.dedent(command.__doc__).strip() if command.__doc__ else ""
                )

                lines.append(f"> {name}:")
                if description:
                    for desc in description.split("\n"):
                        lines.append(f"|    {desc}")
                    lines.append("")

            print("\n".join(lines))
            return

        self.register[args[0]](command=self, args=args[1:])
