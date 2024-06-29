import abc
import argparse
import os
import pathlib
import re
import runpy
import sys
from typing import TYPE_CHECKING

from . import installer

if TYPE_CHECKING:
    from typing_extensions import Self

regexes = {
    "version_specifier": re.compile(r"([^=><]+)(.*)"),
    "name_version_split": re.compile(
        r"^(?P<name>[a-zA-Z0-9][a-zA-Z0-9._-]*(\[[^\]]+\])?)(?P<version>.*)$"
    ),
}


class FailedToGetNameAndVersion(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name

    def __str__(self) -> str:
        return f"A version_file was specified for a local dependency, but couldn't split name and version specifier from result: {self.name}"


class VersionNotSpecified(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name

    def __str__(self) -> str:
        return f"A version_file was specified for a local dependency, but '{{version}}' not found in the name: {self.name}"


def do_format(s: str, **kwargs: object) -> str:
    if hasattr(s, "format"):
        return s.format(**kwargs)
    else:
        return str(s).format(**kwargs)


class Deps(abc.ABC):
    @classmethod
    def from_cli(cls, argv: list[str] | None = None) -> "Self":
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
        parser.add_argument("--venvstarter-force-deps", action="store_true")
        args, _ = parser.parse_known_args(argv)
        return cls(
            project_root=args.venvstarter_project_root,
            uv=args.venvstarter_uv,
            python_path=args.venvstarter_python_path,
            force_deps=args.venvstarter_force_deps,
        )

    def __init__(
        self,
        *,
        project_root: pathlib.Path,
        uv: pathlib.Path,
        python_path: pathlib.Path,
        force_deps: bool,
    ) -> None:
        self.project_root = project_root
        self.uv = uv
        self.force_deps = force_deps
        self.python_path = python_path

        self._requirements_files: list[pathlib.Path] = []
        self._deps: list[str] = []
        self._no_binary: list[str] = []

    @abc.abstractmethod
    def set_requirements(self) -> None:
        pass

    def apply(self) -> None:
        self.set_requirements()
        installer.Installer(
            uv=self.uv,
            python_path=self.python_path,
            deps=self._deps,
            no_binary=self._no_binary,
        ).install(force=self.force_deps)

    def respect_tox(self) -> bool:
        tox_python = os.environ.get("TOX_PYTHON")
        if tox_python:
            self.python_path = pathlib.Path(tox_python)
            return True
        else:
            return False

    def add_requirements_file(
        self, location: pathlib.Path, missing_ok: bool = False
    ) -> None:
        if not location.exists():
            if missing_ok:
                return
            raise ValueError(f"No requirements file at {location}")

        for line in location.read_text().split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                continue
            self._deps.append(line)

    def add_no_binary(self, *no_binary: str) -> None:
        self._no_binary.extend(no_binary)

    def add_deps(self, *deps: str) -> None:
        self._deps.extend(deps)

    def add_local_dep(
        self,
        *,
        name: str,
        path: pathlib.Path,
        version_file: pathlib.Path | None = None,
        editable: bool = True,
        tags: list[str] | None = None,
    ) -> None:
        version = ""
        if version_file is not None:
            version = runpy.run_path(str(version_file))["VERSION"]

            if "{version}" not in name:
                raise VersionNotSpecified(name)

        name = do_format(name, version=version)
        if tags:
            m = regexes["version_specifier"].match(name)
            if m:
                groups = m.groups()
                name = f"{groups[0]}[{','.join(tags)}]{''.join(groups[1:])}"

        just_name_match = regexes["name_version_split"].match(name)
        if not just_name_match:
            raise FailedToGetNameAndVersion(name)

        just_name_groups = just_name_match.groupdict()

        dep = f"{just_name_groups['name']} @ {pathlib.Path(path).resolve().absolute().as_uri()}#egg={name}"

        if editable:
            dep = f"-e {dep}"

        self._deps.append(dep)
