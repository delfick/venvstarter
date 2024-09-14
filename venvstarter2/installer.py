import inspect
import json
import pathlib
import shlex
import subprocess
import tempfile
import textwrap
import urllib.parse

from . import questions


class Installer:
    def __init__(
        self,
        *,
        uv: pathlib.Path,
        python_path: pathlib.Path,
        deps: list[str],
        no_binary: list[str],
    ) -> None:
        self._uv = uv
        self._python_path = python_path
        self._deps = deps
        self._no_binary = no_binary

    def _run_pip(self, *parts: str, check: bool = True) -> int:
        if (
            parts
            and parts[0] == "install"
            and "-t" not in parts
            and "--target" not in parts
        ):
            print(f"### Installing into {self._python_path}")

        process = subprocess.run(
            [str(self._uv), "pip", *parts, "-p", str(self._python_path)],
            check=check,
        )
        return process.returncode

    def _run_question(
        self, question: str, capture_output: bool = True
    ) -> tuple[int, str | None, str | None]:
        process = subprocess.run(
            [str(self._python_path), "-c", textwrap.dedent(question)],
            check=False,
            capture_output=capture_output,
        )
        return (
            process.returncode,
            None if process.stdout is None else process.stdout.decode(),
            None if process.stderr is None else process.stderr.decode(),
        )

    def _check_deps(self) -> int:
        deps_to_use = []

        for dep in self._deps:
            original_dep = dep
            name = None

            if dep.count("@") == 1:
                name, dep = dep.split("@", 1)
                name = name.strip()
                dep = dep.strip()
            elif dep.count("@") == 2:
                name, _ = dep.split("@", 1)
                name = name.strip()

            if "#" in dep:
                if "egg" in dep:
                    dep = dict(
                        arg.split("=", 1) for arg in dep.split("#", 1)[1].split("&")
                    )["egg"]
                else:
                    parsed = urllib.parse.urlparse(dep)
                    version_specifier = parsed.query
                    if "?" in parsed.query:
                        version_specifier = parsed.query.split("?")[0]

                    if parsed.fragment and not name:
                        name = parsed.fragment

                    if not name:
                        raise ValueError(
                            f"Couldn't determine dependency name from {original_dep}"
                        )

                    dep = f"{name}{version_specifier}"

            deps_to_use.append(dep)

        question = "\n".join(
            [
                inspect.getsource(questions.determine_if_needs_installation),
                f"\ndetermine_if_needs_installation({json.dumps(str(self._uv))}, {json.dumps(deps_to_use)}, {json.dumps(self._no_binary)})",
            ]
        )
        ret, _, _ = self._run_question(question, capture_output=False)
        return ret

    def _find_deps_to_be_made_not_binary(self) -> list[str]:
        question = f"""
        import importlib

        for name in {json.dumps(self._no_binary)}:
            try:
                if importlib.import_module(name).__file__.endswith(".so"):
                    print(name)
            except ImportError:
                pass
        """

        ret, stdout, stderr = self._run_question(question)
        if ret != 0 or stdout is None:
            raise RuntimeError(
                f"Failed to get deps to be made not binary: {ret=}\n{stdout=}\n{stderr=}"
            )

        return [
            shlex.quote(name.strip()) for name in stdout.split("\n") if name.strip()
        ]

    def install(self, force: bool = False) -> None:
        ret = self._check_deps()
        if ret != 0 or force:
            ret = 1
            reqs = None
            try:
                to_remove = self._find_deps_to_be_made_not_binary()
                if to_remove:
                    self._run_pip("uninstall", "-y", *to_remove)

                reqs = tempfile.NamedTemporaryFile(
                    delete=False, suffix="venvstarter_requirements", dir="."
                )
                for dep in self._deps:
                    reqs.write(f"\n{dep}".encode())

                for dep in self._no_binary:
                    reqs.write(f"\n--no-binary {dep}".encode())

                reqs.close()
                ret = self._run_pip("install", "-r", reqs.name)
            finally:
                if reqs is not None:
                    reqs_loc = pathlib.Path(reqs.name)
                if reqs is not None and reqs_loc.exists():
                    reqs_loc.unlink()

            if ret != 0:
                raise SystemExit(1)

            ret = self._check_deps()
            if ret != 0:
                raise Exception("Couldn't install the requirements")
