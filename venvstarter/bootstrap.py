import argparse
import os
import pathlib
import shlex
import shutil
import subprocess
import sys
from itertools import chain


def python_from(
    venv_folder,  # type: pathlib.Path
):  # type: pathlib.Path | None
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
    def __init__(
        self,
        python_acceptable,  # type: Callable[[pathlib.Path | str], bool]
    ):  # type: None
        self.python_acceptable = python_acceptable

    def discover(self):  # type: pathlib.Path | None
        python = self.try_path()

        if not python:
            python = self.try_asdf()
        if not python:
            python = self.try_pyenv()

        return python

    def try_asdf(self):  # type: pathlib.Path |None
        if not shutil.which("asdf"):
            return

        want = None  # type: str | None

        try:
            print("## Trying to find a suitable python with asdf")
            process = subprocess.run(
                ["asdf", "list", "python"], check=True, capture_output=True
            )
        except subprocess.CalledProcessError:
            return
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
            return

        try:
            process = subprocess.run(
                ["asdf", "where", "python", want], check=True, capture_output=True
            )
        except subprocess.CalledProcessError:
            return
        else:
            print(f"## Using python {want} from asdf")
            return pathlib.Path(process.stdout.decode())

    def try_pyenv(self):  # type: pathlib.Path |None
        if not shutil.which("pyenv"):
            return

        want = None  # type: str | None

        try:
            print("## Trying to find a suitable python with pyenv")
            process = subprocess.run(
                ["pyenv", "versions"], check=True, capture_output=True
            )
        except subprocess.CalledProcessError:
            return
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
            return

        try:
            process = subprocess.run(
                ["pyenv", "which", "python"],
                check=True,
                capture_output=True,
                env={**os.environ, "PYENV_VERSION": want},
            )
        except subprocess.CalledProcessError:
            return
        else:
            print(f"## Using python {want} from pyenv")
            return pathlib.Path(process.stdout.decode())

    def try_path(self):  # type: pathlib.Path |None
        if self.python_acceptable(pathlib.Path(sys.executable)):
            return pathlib.Path(sys.executable)

        py3 = shutil.which("python3")
        if py3 and self.python_acceptable(py3):
            return pathlib.Path(py3)

        py = shutil.which("python")
        if py and self.python_acceptable(py):
            return pathlib.Path(py)


class Bootstrap:
    def __init__(
        self,
        project_root,  # type: pathlib.Path
        python_version,  # type: str
        version,  # type :str
        manager,  # type:pathlib.Path
        uv,  # type:pathlib.Path
        program_args,  # type: list[str]
        venv_location,  # type: pathlib.Path
        original_venv,  # type: pathlib.Path | None
        get_activate_script,  # type: pathlib.Path | None
        venv_only,  # type: bool
        manual_marker=None,  # type: pathlib.Path | None
    ):  # type: None
        self.uv = uv
        self.python_version = python_version
        self.venv_only = venv_only
        self.version = version
        self.manager = manager
        self.project_root = project_root
        self.program_args = program_args
        self.venv_location = venv_location
        self.original_venv = original_venv
        self.manual_marker = manual_marker
        self.get_activate_script = get_activate_script

    def __repr__(self):  # type: str
        return "\n".join(
            [
                "Bootstrap:",
                f"{self.project_root=}",
                f"{self.python=}",
                f"{self.version=}",
                f"{self.manager=}",
                f"{self.uv=}",
                f"{self.program_args=}",
            ]
        )

    def bootstrap(self):  # type: None
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

        if not self.venv_location.exists():
            python = self._ensure_python()
            subprocess.run(
                [self.uv, "venv", str(self.venv_location), "-p", str(python)],
                check=True,
            )

        python = python_from(self.venv_location)
        if not python:
            sys.exit("!!! Failed to get a virtualenv to use")

        ensure_venvstarter = True
        if self.version == "-e ." or self.version.startswith("-e .["):
            try:
                process = subprocess.run(
                    [self.uv, "pip", "freeze", "-p", str(python)],
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError:
                pass
            else:
                version = f"-e file://{self.project_root}{self.version[4:]}"
                if version.encode() in process.stdout:
                    ensure_venvstarter = False

        if ensure_venvstarter:
            subprocess.run(
                [
                    self.uv,
                    "pip",
                    "install",
                    *shlex.split(self.version),
                    "-p",
                    str(python),
                ],
                check=True,
                cwd=self.project_root,
            )

        if self.venv_only:
            return

        if self.get_activate_script:
            self.get_activate_script.write_text(str(python.parent / "activate"))
            sys.exit(0)

        os.execve(
            str(python),
            [str(python), str(self.manager), *self.program_args],
            {**os.environ, "VENVSTARTER_UV": str(self.uv)},
        )

    def compare_versions(
        self,
        have,  # type: str
        want,  # type: str
    ):  # type: bool
        from packaging.specifiers import SpecifierSet
        from packaging.version import Version

        return Version(have) in SpecifierSet(want)

    def _ensure_python(self):  # type: None
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

        return python

    def _ask_about_python(
        self,
        manual_marker,  # type: pathlib.Path
    ):  # type: pathlib.Path | None
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
            provided = self.original_venv
        else:
            while True:
                try:
                    provided = input("Enter path to virtualenv to use: ")
                except (EOFError, KeyboardInterrupt):
                    sys.exit(1)
                if not provided.exists():
                    print("The path entered doesn't exist, try again or press ctrl-c")
                else:
                    break

        found = python_from(provided)
        if found:
            print(f"## To go back to a managed virtualenv, delete '{manual_marker}'")
            return found

        sys.exit("!! Failed to find a python to use in '{provided}'")

    def _python_version_is_acceptable(
        self,
        python,  # type: pathlib.Path | str
    ):  # type: bool
        if isinstance(python, str):
            return self.compare_versions(python.strip(), self.python_version)

        try:
            process = subprocess.run(
                [str(python), "--version"], capture_output=True, check=True
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
            version = process.stdout.decode().split(" ")[1].strip()
            return self.compare_versions(version, self.python_version)


def make_parser(
    default_project_root,  # type: pathlib.Path
    default_python=">=3.10",  # type: str
    default_venvstarter=">=0.13.0",  # type: str
    default_manager=pathlib.Path("./manager.py"),  # type: pathlib.Path
    default_uv=pathlib.Path("./bootstrap_uv.sh"),  # type: pathlib.Path
    default_venv_location=pathlib.Path("./.python"),  # type: pathlib.Path
    default_venv_only=False,  # type: bool
    default_manual_marker=None,  # type:pathlib.Path | None
    default_original_venv=None,  # type: pathlib.Path | None,
):  # type: argparse.ArgumentParser
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--venvstarter-python",
        default=default_python,
        help="The python range acceptable for this environment",
    )
    parser.add_argument(
        "--venvstarter-version",
        default=default_venvstarter,
        help="The version range for venvstarter acceptable for this environment",
    )
    parser.add_argument(
        "--venvstarter-manager",
        default=default_manager,
        type=pathlib.Path,
        help="The path to the manager.py to use, relative to PROJECT_ROOT",
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
        "--venvstarter-venv-only", action="store_true", help="Only create the venv"
    )
    parser.add_argument(
        "--venvstarter-get-activate-script",
        type=pathlib.Path,
        help="Path to write the location of the activate script to for activating the virtual env",
    )

    parser.add_argument(
        "--venvstarter-original-venv",
        default=default_original_venv,
        type=pathlib.Path,
        help="The virtualenv to be considered active before bootstrapping began",
    )

    return parser


def main(
    argv=None,  # type: list[str] | None
):  # type: None
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
        default_project_root=pathlib.Path(os.environ["VENVSTARTER_PROJECT_ROOT"])
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
            default_venvstarter=args.venvstarter_version,
            default_manager=args.venvstarter_manager,
            default_uv=args.venvstarter_uv,
            default_venv_location=args.venvstarter_venv_location,
            default_manual_marker=args.venvstarter_manual_marker,
            default_venv_only=args.venvstarter_venv_only,
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
        version=args.venvstarter_version,
        manager=project_root / args.venvstarter_manager,
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
