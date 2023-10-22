import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap

from . import errors
from . import helpers as hp

regexes = {
    "version_specifier": re.compile(r"([^=><]+)(.*)"),
    "version_string": re.compile(r"^([^\.]+)(?:\.([^\.]+))?(?:\.([^\.]+))?.*"),
}


class Version:
    def __init__(self, version, without_patch=False):
        original = version

        if isinstance(version, Version):
            version = str(version)

        if isinstance(version, (int, float)):
            version = str(version)
        elif hasattr(version, "version"):
            version = version.version

        if isinstance(version, (list, tuple)):
            while len(version) < 3:
                version = (*version, 0)
            version = f"{version[0]}.{version[1]}.{version[2]}"

        if not isinstance(version, str):
            raise errors.InvalidVersion(original)

        m = regexes["version_string"].match(version)
        if m is None:
            raise errors.InvalidVersion(version)

        groups = m.groups()
        self.major = int(groups[0])
        self.minor = int(groups[1] or "0")
        self.patch = int(groups[2] or "0")

        self.without_patch = without_patch
        if without_patch:
            self.patch = 0

    @property
    def version(self):
        return (self.major, self.minor, self.patch)

    def __str__(self):
        return f"{self.major}.{self.minor}.{self.patch}"

    def __repr__(self):
        return f"<Version {str(self)}>"

    def __eq__(self, other):
        return self._cmp(other) == 0

    def __lt__(self, other):
        return self._cmp(other) < 0

    def __le__(self, other):
        return self._cmp(other) <= 0

    def __gt__(self, other):
        return self._cmp(other) > 0

    def __ge__(self, other):
        return self._cmp(other) >= 0

    def _cmp(self, other):
        this = self.version
        other = Version(other).version

        if self.without_patch:
            this = this[:2]
            other = other[:2]

        if this != other:
            if this < other:
                return -1
            else:
                return 1

        return 0


class Shebang:
    def __init__(self, *cmd):
        self.cmd = cmd

    def produce(self, only_for_windows=False):
        cmd = self.cmd
        if not cmd:
            return

        if only_for_windows and os.name != "nt":
            yield from cmd
            return

        with open(pathlib.Path(cmd[0]).resolve()) as fle:
            try:
                part = fle.read(2)
            except UnicodeDecodeError:
                part = ""

            if part == "#!":
                shb = fle.readline().strip()
                if os.name == "nt":
                    if " " in shb:
                        if pathlib.Path(shb.split(" ")[0]).name == "env":
                            shb = shb[shb.find(" ") + 1 :]
                    yield shb
                else:
                    yield from shlex.split(shb)

        yield from cmd


class PythonHandler:
    def __init__(self, min_python=3, max_python=3):
        self._min_python = min_python
        self._max_python = max_python

    @hp.memoized_property
    def min_python(self):
        if self._min_python is None:
            return None
        return Version(self._min_python, without_patch=True)

    @hp.memoized_property
    def max_python(self):
        if self._max_python is None:
            return None
        return Version(self._max_python, without_patch=True)

    def suitable(self, version):
        if version is None:
            return False

        if version < self.min_python:
            return False

        if self.max_python is not None and version > self.max_python:
            return False

        return True

    def with_shebang(self, *cmd, only_for_windows=False):
        return Shebang(*cmd).produce(only_for_windows=only_for_windows)

    def get_output(self, python_exe, script, **kwargs):
        return self.run_command(python_exe, script, get_output=True, **kwargs)

    def run_command(self, python_exe, script, get_output=False, **kwargs):
        fle = None
        try:
            fle = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)
            fle.write(textwrap.dedent(script))
            fle.close()

            question = [
                str(q) for q in self.with_shebang(python_exe, fle.name, only_for_windows=True)
            ]
            if get_output:
                return (
                    (subprocess.check_output(question, **{"stderr": subprocess.PIPE, **kwargs}))
                    .strip()
                    .decode()
                )
            else:
                return subprocess.run(question, **{"check": True, **kwargs})
        except subprocess.CalledProcessError as error:
            stde = ""
            if error.stderr:
                stde = error.stderr.decode()
            raise errors.FailedToGetOutput(stde, error)
        finally:
            location = pathlib.Path(fle.name)
            if fle is not None and location.exists():
                location.unlink()

    def version_for(self, executable, raise_error=False, without_patch=False):
        if executable is None:
            return None, None

        try:
            version_info = self.get_output(
                executable, 'print(__import__("json").dumps(list(__import__("sys").version_info)))'
            )
        except errors.FailedToGetOutput:
            if raise_error:
                raise
            return executable, None

        if version_info:
            version_info = version_info.split("\n")[-1]

        try:
            vers = ".".join(str(part) for part in json.loads(version_info))
        except (TypeError, ValueError) as error:
            raise Exception(
                f"Failed to figure out python version\nLooking at:\n=====\n{version_info}\n=====\nError: {error}"
            )
        else:
            return executable, Version(vers, without_patch=without_patch)

    def versions(self, starting):
        version = starting
        while version < self.min_python:
            if version.major > self.min_python.major:
                version = Version(version.major + 1)
            else:
                version = Version((version.major + 1, version.minor + 1))

        while version >= self.min_python:
            yield "python{0}.{1}".format(*version.version)

            if version.version[1] == 0:
                if version.version[0] == 0:
                    break

                version = Version((version.major - 1))
            else:
                version = Version((version.major, version.minor - 1))

        version = starting
        while version >= self.min_python:
            yield "python{0}".format(*version.version)

            if version.version[0] <= 3:
                break

            version = Version(version.major - 1)

        yield "python"

    def find(self):
        if self.max_python is None:
            ex, version = self.version_for(sys.executable, without_patch=True)
            if self.suitable(version):
                return sys.executable

        max_python = self.min_python
        if self.max_python is None:
            _, max_python_1 = self.version_for(shutil.which("python3"), without_patch=True)
            _, max_python_2 = self.version_for(shutil.which("python"), without_patch=True)
            found = [
                m for m in (max_python_1, max_python_2) if m is not None and m > self.min_python
            ]
            if len(found) > 1:
                max_python = max([max_python_1, max_python_2])
            elif len(found) == 1:
                max_python = found[0]
        else:
            max_python = self.max_python

        tried = []
        for version in self.versions(max_python):
            tried.append(version)
            executable, found = self.version_for(shutil.which(version), without_patch=True)
            if self.suitable(found):
                return executable

        raise Exception(
            "\n".join(
                [
                    "\nCouldn't find a suitable python!",
                    f"Wanted between {self.min_python} and {max_python}",
                    f"Tried {', '.join(tried)}",
                ]
            )
        )
