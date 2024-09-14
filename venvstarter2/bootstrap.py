import argparse
import os
import pathlib
import shutil
import subprocess
import sys
from itertools import chain
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    Callable = Callable


def python_from(venv_folder):
    # type: (pathlib.Path) -> pathlib.Path | None
    if venv_folder.name in ("python", "python3") and venv_folder.is_file():
        return venv_folder

    if os.name == "nt":
        location = venv_folder / "Scripts" / "python"
    else:
        location = venv_folder / "bin" / "python"

    if location.exists():
        return location

    if os.name == "nt":
        exe = location.with_suffix(".exe")
        if exe.exists():
            return exe

    return None


class PythonDiscovery:
    def __init__(self, python_acceptable):
        # type: (Callable[[pathlib.Path | str], bool]) -> None
        self.python_acceptable = python_acceptable

    def discover(self):
        # type: () -> pathlib.Path | None
        python = self.try_path()

        if not python:
            python = self.try_asdf()
        if not python:
            python = self.try_pyenv()

        return python

    def try_asdf(self):
        # type: () -> pathlib.Path | None
        if not shutil.which("asdf"):
            return None

        want = None  # type: str | None

        try:
            print("## Trying to find a suitable python with asdf")
            process = subprocess.run(
                ["asdf", "list", "python"], check=True, capture_output=True
            )
        except subprocess.CalledProcessError:
            return None
        else:
            versions = set()  # type: set[str]
            for version in process.stdout.decode().split("\n"):
                version = version.strip()
                while version.startswith("*"):
                    version = version[1:]
                if not version:
                    continue
                versions.add(version)

            for version in reversed(
                sorted(
                    versions,
                    key=lambda v: tuple(
                        int(k) if k.isdigit() else k for k in v.split(".")
                    ),
                )
            ):
                if self.python_acceptable(version):
                    want = version
                    break

        if want is None:
            return None

        try:
            process = subprocess.run(
                ["asdf", "where", "python", want], check=True, capture_output=True
            )
        except subprocess.CalledProcessError:
            return None
        else:
            print(f"## Using python {want} from asdf")
            return pathlib.Path(process.stdout.decode().strip())

    def try_pyenv(self):
        # type: () -> pathlib.Path | None
        if not shutil.which("pyenv"):
            return None

        want = None  # type: str | None

        try:
            print("## Trying to find a suitable python with pyenv")
            process = subprocess.run(
                ["pyenv", "versions"], check=True, capture_output=True
            )
        except subprocess.CalledProcessError:
            return None
        else:
            versions = set()  # type: set[str]
            for version in process.stdout.decode().split("\n"):
                version = version.strip()
                while version.startswith("*"):
                    version = version[1:]
                if version.strip().startswith("system"):
                    continue
                if not version:
                    continue
                versions.add(version)

            for version in reversed(
                sorted(
                    versions,
                    key=lambda v: tuple(
                        int(k) if k.isdigit() else k for k in v.split(".")
                    ),
                )
            ):
                if self.python_acceptable(version):
                    want = version
                    break

        if want is None:
            return None

        try:
            process = subprocess.run(
                ["pyenv", "which", "python"],
                check=True,
                capture_output=True,
                env={**os.environ, "PYENV_VERSION": want},
            )
        except subprocess.CalledProcessError:
            return None
        else:
            print(f"## Using python {want} from pyenv")
            return pathlib.Path(process.stdout.decode().strip())

    def try_path(self):
        # type: () -> pathlib.Path | None
        if self.python_acceptable(pathlib.Path(sys.executable)):
            return pathlib.Path(sys.executable)

        py3 = shutil.which("python3")
        if py3 and self.python_acceptable(pathlib.Path(py3.strip())):
            return pathlib.Path(py3.strip())

        py = shutil.which("python")
        if py and self.python_acceptable(pathlib.Path(py.strip())):
            return pathlib.Path(py.strip())

        return None


class Bootstrap:
    def __init__(
        self,
        project_root,
        python_version,
        deps_manager,
        tools_manager,
        uv,
        program_args,
        venv_location,
        original_venv,
        get_activate_script,
        venv_only,
        manual_marker=None,
    ):
        # type: (pathlib.Path, str, pathlib.Path | None, pathlib.Path | None, pathlib.Path, list[str], pathlib.Path, pathlib.Path | None, pathlib.Path | None, bool, pathlib.Path | None) -> None
        self.uv = uv
        self.python_version = python_version
        self.venv_only = venv_only
        self.deps_manager = deps_manager
        self.tools_manager = tools_manager
        self.project_root = project_root
        self.program_args = program_args
        self.venv_location = venv_location
        self.original_venv = original_venv
        self.manual_marker = manual_marker
        self.get_activate_script = get_activate_script

    def bootstrap(self):
        # type: () -> None
        needs_packaging = False
        try:
            __import__("packaging")
        except ImportError:
            if "VENVSTARTER_ASSUME_PACKAGING" in os.environ:
                sys.exit("!!! Failed to bootstrap 'packaging' package")

            needs_packaging = True

        if needs_packaging:
            try:
                print("## Need to bootstrap the packaging package")
                subprocess.run(
                    [str(self.uv), "pip", "install", "packaging", "-p", sys.executable],
                    cwd=pathlib.Path.cwd(),
                    check=True,
                )
            except subprocess.CalledProcessError:
                sys.exit("!!! Failed to bootstrap")
            else:
                argv = sys.argv
                if sys.argv[0] == __file__:
                    argv = [sys.executable, *sys.argv]

                os.execve(
                    sys.executable,
                    argv,
                    {**os.environ, "VENVSTARTER_ASSUME_PACKAGING": "1"},
                )

        previous_manual_venv = None  # type: pathlib.Path | None
        if self.manual_marker and self.manual_marker.exists():
            previous_manual_venv = pathlib.Path(self.manual_marker.read_text())

        if not self.venv_location.exists():
            python = self._ensure_python()
        else:
            found = python_from(self.venv_location)
            if not found:
                sys.exit("!!! Failed to get a virtualenv to use")
            else:
                python = found

        env = {**os.environ, "VENVSTARTER_UV": str(self.uv)}

        # Fix a bug whereby the virtualenv has the wrong sys.executable
        if "__PYVENV_LAUNCHER__" in env:
            del env["__PYVENV_LAUNCHER__"]

        if self.deps_manager:
            install_deps = True
            if self.manual_marker is not None and self.manual_marker.exists():
                if (
                    pathlib.Path(self.manual_marker.read_text().strip())
                    == previous_manual_venv
                ):
                    install_deps = False
                else:
                    print(
                        f"Would you like to install this project into your venv ({python})?"
                    )
                    answer = None  # type: str | None
                    while answer is None:
                        try:
                            answer = input("(y/n): ")
                        except (EOFError, KeyboardInterrupt):
                            sys.exit(1)
                        else:
                            if answer not in ("y", "n"):
                                answer = None
                                print("!!! Please say 'y' or 'n'")

                    install_deps = answer == "y"

            if install_deps or "--venvstarter-force-deps" in self.program_args:
                manage_deps = [
                    a for a in self.program_args if a not in ("-h", "--help")
                ]
                if "--venvstarter-python-path" not in self.program_args:
                    manage_deps.extend(["--venvstarter-python-path", str(python)])

                try:
                    subprocess.run(
                        [sys.executable, str(self.deps_manager), *manage_deps],
                        env=env,
                        check=True,
                    )
                except subprocess.CalledProcessError:
                    sys.exit("!!! Failed to update dependencies")

        if self.venv_only:
            return None

        if self.get_activate_script:
            self.get_activate_script.write_text(str(python.parent / "activate"))
            sys.exit(0)

        tools_manager = self.tools_manager
        if tools_manager is None:
            os.execve(str(python), [str(python), *self.program_args], env)

        if str(tools_manager).startswith(":"):
            tools_manager = pathlib.Path(
                str(tools_manager).replace(":", f"{str(python.parent)}{os.sep}", 1)
            )

        os.execve(
            str(python), [str(python), str(tools_manager), *self.program_args], env
        )

    def compare_versions(self, have, want):
        # type: (str, str) -> bool
        from packaging.specifiers import SpecifierSet
        from packaging.version import Version

        return Version(have) in SpecifierSet(want)

    def _ensure_python(self):
        # type: () -> pathlib.Path
        python = None  # type: pathlib.Path | None
        if self.manual_marker is not None:
            if self.manual_marker.exists():
                python = pathlib.Path(self.manual_marker.read_text().strip())
                if not python.exists():
                    print(
                        f"> Found manual marker but it specifies a python that doesn't exist ({python})"
                    )
                    print("How should we proceed?:")
                    python = self._ask_about_python(self.manual_marker)

            if python is None and not self.venv_location.exists():
                if "CI" not in os.environ:
                    print("> No virtual env exists")
                    python = self._ask_about_python(self.manual_marker)

            if python is not None:
                while python and not self._python_version_is_acceptable(python):
                    print(
                        f"!!! manually managed python at {python} isn't compatible with version specified {self.python_version}"
                    )
                    python = self._ask_about_python(self.manual_marker)

                if python:
                    return python

        if self.venv_location.exists():
            existing_python = python_from(self.venv_location)
            if existing_python is None or not self._python_version_is_acceptable(
                existing_python
            ):
                shutil.rmtree(self.venv_location)
            else:
                python = existing_python
        else:
            python = PythonDiscovery(
                python_acceptable=self._python_version_is_acceptable
            ).discover()

        if not python:
            print("!!! Failed to find a suitable python")
            sys.exit(1)

        if not self.venv_location.exists():
            subprocess.run(
                [str(self.uv), "venv", str(self.venv_location), "-p", str(python)],
                check=True,
            )
            python = python_from(self.venv_location)
            if not python:
                sys.exit(
                    f"!!! Failed to find python in the venv we just created: {self.venv_location}"
                )

        return python

    def _ask_about_python(self, manual_marker):
        # type: (pathlib.Path) -> pathlib.Path | None
        print("How should we proceed?:")
        print("1) Let venvstarter manage the virtualenv")
        print(
            f"2) Use virtualenv you already have active? ({'No virtual env currently active' if self.original_venv is None else self.original_venv})"
        )
        print("3) Some other virtualenv?")
        print("q) exit")
        while True:
            try:
                answer = input("> ")
            except (EOFError, KeyboardInterrupt):
                sys.exit(1)
            if answer.strip() not in ("1", "2", "3", "q"):
                print(f"'{answer}' isn't one of the options")
                continue
            else:
                if answer == "q":
                    sys.exit(1)
                break

        if answer == "1":
            manual_marker.unlink(missing_ok=True)
            return None
        elif answer == "2":
            if self.original_venv is None:
                print("!!! No active virtual env already, activate one and try again")
                sys.exit(1)
            provided = python_from(self.original_venv)
            if not provided:
                print("!!! Failed to find python from active virtual env")
                sys.exit(1)
        else:
            while True:
                try:
                    provided = pathlib.Path(
                        input("Enter path to virtualenv to use: ").strip()
                    )
                except (EOFError, KeyboardInterrupt):
                    sys.exit(1)
                if not provided.exists():
                    print("The path entered doesn't exist, try again or press ctrl-c")
                else:
                    break

        found = python_from(provided)
        if found:
            print(f"## To go back to a managed virtualenv, delete '{manual_marker}'")
            manual_marker.write_text(str(found))
            return found

        sys.exit(f"!! Failed to find a python to use in '{provided}'")

    def _python_version_is_acceptable(self, python):
        # type: (pathlib.Path | str) -> bool
        if isinstance(python, str):
            return self.compare_versions(python.strip(), self.python_version)

        if not python.is_file():
            return False

        try:
            process = subprocess.run(
                [str(python), "-c", 'print(__import__("sys").version.split(" ")[0])'],
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as error:
            print("!!! Failed to get python version")
            print(f"!!! Ran > {python} --version")
            for line in error.stdout.split(b"\n"):
                print(f"!!! stdout: {line!r}")
            for line in error.stderr.split(b"\n"):
                print(f"!!! stderr: {line!r}")

            return False
        else:
            version = process.stdout.decode().strip()
            return self.compare_versions(version, self.python_version)


def make_parser(
    default_project_root,
    default_python=">=3.10",
    default_deps_manager=None,
    default_tools_manager=None,
    default_uv=pathlib.Path("./bootstrap_uv.sh"),
    default_venv_location=pathlib.Path("./.python"),
    default_venv_only=False,
    default_manual_marker=None,
    default_original_venv=None,
    default_get_activate_script=None,
    default_assume_correct_deps=False,
):
    # type: (pathlib.Path, str, pathlib.Path | None, pathlib.Path | None, pathlib.Path, pathlib.Path, bool, pathlib.Path | None, pathlib.Path | None, pathlib.Path | None, bool) -> argparse.ArgumentParser

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--venvstarter-python",
        default=default_python,
        help="The python range acceptable for this environment",
    )
    parser.add_argument(
        "--venvstarter-deps-manager",
        default=default_deps_manager,
        type=pathlib.Path,
        help="The path to the manager.py to use for ensuring dependencies are correct, relative to PROJECT_ROOT",
    )
    parser.add_argument(
        "--venvstarter-tools-manager",
        default=default_tools_manager,
        type=pathlib.Path,
        help="The path to the manager.py to use for determining what command to run, relative to PROJECT_ROOT",
    )
    parser.add_argument(
        "--venvstarter-uv",
        default=default_uv,
        type=pathlib.Path,
        help="The path to a uv binary, relative to PROJECT_ROOT",
    )
    parser.add_argument(
        "--venvstarter-project-root",
        default=default_project_root,
        type=pathlib.Path,
        help="The path to the root of this project",
    )
    parser.add_argument(
        "--venvstarter-venv-location",
        default=default_venv_location,
        type=pathlib.Path,
        help="Path to where the managed virtualenv will go",
    )
    parser.add_argument(
        "--venvstarter-manual-marker",
        default=default_manual_marker,
        type=pathlib.Path,
        required=False,
        help="The path to a file that would tell venvstarter to not manage the virtualenv",
    )
    parser.add_argument(
        "--venvstarter-venv-only",
        action="store_true",
        help="Only create the venv",
        default=default_venv_only,
    )
    parser.add_argument(
        "--venvstarter-get-activate-script",
        type=pathlib.Path,
        default=default_get_activate_script,
        help="Path to write the location of the activate script to for activating the virtual env",
    )
    parser.add_argument(
        "--venvstarter-assume-correct-deps",
        action="store_true",
        default=default_assume_correct_deps,
        help="Don't check whether the dependencies are correct",
    )
    parser.add_argument(
        "--venvstarter-original-venv",
        default=default_original_venv,
        type=pathlib.Path,
        help="The virtualenv to be considered active before bootstrapping began",
    )

    return parser


def main(argv=None):
    # type: (list[str] | None) -> None
    if "VENVSTARTER_PROJECT_ROOT" not in os.environ:
        sys.exit(
            "venvstarter bootstrap requires a VENVSTARTER_PROJECT_ROOT environment variable"
        )

    if argv is None:
        argv = sys.argv[1:]

    if "--" not in argv:
        venvstarter_args = argv
        program_args = []
    else:
        double_dash = argv.index("--")
        venvstarter_args = argv[:double_dash]
        program_args = argv[double_dash + 1 :]

    parser = make_parser(
        default_project_root=pathlib.Path(
            os.environ["VENVSTARTER_PROJECT_ROOT"].strip()
        )
    )
    args = parser.parse_args(venvstarter_args)

    relevant_flags = list(
        chain.from_iterable(
            [
                a.option_strings
                for a in parser._actions
                if "--help" not in a.option_strings
            ]
        )
    )
    if any(flag in program_args for flag in relevant_flags):
        contains_help = "-h" in program_args or "--help" in program_args
        parser = make_parser(
            default_project_root=args.venvstarter_project_root,
            default_original_venv=args.venvstarter_original_venv,
            default_python=args.venvstarter_python,
            default_deps_manager=args.venvstarter_deps_manager,
            default_tools_manager=args.venvstarter_tools_manager,
            default_uv=args.venvstarter_uv,
            default_venv_location=args.venvstarter_venv_location,
            default_manual_marker=args.venvstarter_manual_marker,
            default_venv_only=args.venvstarter_venv_only,
            default_get_activate_script=args.venvstarter_get_activate_script,
            default_assume_correct_deps=args.venvstarter_assume_correct_deps,
        )
        args, program_args = parser.parse_known_args(
            [a for a in program_args if a not in ("-h", "--help")]
        )
        if contains_help:
            program_args.append("--help")

    project_root = args.venvstarter_project_root.resolve()

    Bootstrap(
        project_root=project_root,
        python_version=args.venvstarter_python,
        deps_manager=(
            project_root / args.venvstarter_deps_manager
            if args.venvstarter_deps_manager
            and not args.venvstarter_assume_correct_deps
            else None
        ),
        tools_manager=(
            project_root / args.venvstarter_tools_manager
            if args.venvstarter_tools_manager
            else None
        ),
        uv=project_root / args.venvstarter_uv,
        venv_location=project_root / args.venvstarter_venv_location,
        manual_marker=project_root / args.venvstarter_manual_marker,
        venv_only=args.venvstarter_venv_only,
        get_activate_script=args.venvstarter_get_activate_script,
        original_venv=(
            None
            if str(args.venvstarter_original_venv) == "-"
            else args.venvstarter_original_venv
        ),
        program_args=program_args,
    ).bootstrap()


if __name__ == "__main__":
    main()
