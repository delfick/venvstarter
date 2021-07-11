"""
A program to manage your program in a virtualenv and ensure it and any other
dependencies you may have are in that virtualenv before starting the program.

It allows the creation of a shell script like the following::

    #!/usr/bin/env python3

    (
        __import__("venvstarter").manager("harpoon")
        .add_pypi_deps("docker-harpoon==0.12.1")
        .add_env(HARPOON_CONFIG=("{venv_parent}","harpoon.yml"))
        .run()
    )

Such that running the script will ensure a Python virtualenv exists with the
correct dependencies before running a particular program using that virtualenv
with the rest of the arguments given on the command line.

.. note::
    A disadvantage of this system is that there is a small cost to starting
    the script when it determines if the virtualenv has all the correct
    versions of dependencies present.

    If you want to skip checking the versions of your dependencies, then set
    VENV_STARTER_CHECK_DEPS=0 in your environment.
"""
from textwrap import dedent
from pathlib import Path
import subprocess
import tempfile
import inspect
import shutil
import runpy
import shlex
import json
import sys
import os
import re

VERSION = "0.9.0"

regexes = {
    "version_specifier": re.compile(r"([^=><]+)(.*)"),
    "ascii": re.compile(r"([a-zA-Z]+(0-9)*)+"),
    "version_string": re.compile(r"^([^\.]+)(?:\.([^\.]+))?(?:\.([^\.]+))?.*"),
}


def do_format(s, **kwargs):
    if hasattr(s, "format"):
        return s.format(**kwargs)
    else:
        return str(s).format(**kwargs)


class FailedToGetOutput(Exception):
    def __init__(self, error, stderr):
        self.error = error
        self.stderr = stderr

    def __str__(self):
        return f"Failed to get output\nstderr: {self.stderr}\nerror: {self.error}"


class VersionNotSpecified(Exception):
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return f"A version_file was specified for a local dependency, but '{{version}}' not found in the name: {self.name}"


class InvalidVersion(Exception):
    def __init__(self, want):
        self.want = want

    def __str__(self):
        return f"Version needs to be an int, float or string, got {self.want}"


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
            raise InvalidVersion(original)

        m = regexes["version_string"].match(version)
        if m is None:
            raise InvalidVersion(version)

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


class memoized_property(object):
    def __init__(self, func):
        self.func = func
        self.key = f".{self.func.__name__}"

    def __get__(self, instance, owner):
        obj = getattr(instance, self.key, None)
        if obj is None:
            obj = self.func(instance)
            setattr(instance, self.key, obj)
        return obj

    def __set__(self, instance, value):
        setattr(instance, self.key, value)


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

        with open(Path(cmd[0]).resolve()) as fle:
            try:
                part = fle.read(2)
            except UnicodeDecodeError:
                part = ""

            if part == "#!":
                shb = fle.readline().strip()
                if os.name == "nt":
                    if " " in shb:
                        if Path(shb.split(" ")[0]).name == "env":
                            shb = shb[shb.find(" ") + 1 :]
                    yield shb
                else:
                    yield from shlex.split(shb)

        yield from cmd


class PythonHandler:
    def __init__(self, min_python=3, max_python=3):
        self._min_python = min_python
        self._max_python = max_python

    @memoized_property
    def min_python(self):
        if self._min_python is None:
            return None
        return Version(self._min_python, without_patch=True)

    @memoized_property
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
            fle.write(dedent(script))
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
            raise FailedToGetOutput(stde, error)
        finally:
            location = Path(fle.name)
            if fle is not None and location.exists():
                location.unlink()

    def version_for(self, executable, raise_error=False, without_patch=False):
        if executable is None:
            return None, None

        try:
            version_info = self.get_output(
                executable, 'print(__import__("json").dumps(list(__import__("sys").version_info)))'
            )
        except FailedToGetOutput:
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


class Starter(object):
    """
    The main class that knows how to manage the virtualenv

    venv_folder
        A folder that the virtualenv will sit in.

        Note that if you pass in the location of a file, it will use the folder
        that file sits in. This is convenient so you can just pass in __file__
        from your bootstrap script.

    program
        The program to run as None, a list, a string or as a function.

        If set as None, then the python in the virtualenv is run

        If the program is given as a string, we invoke it from the scripts in the
        virtualenv.

        If the program is given as a list, then we `os.execve(result[0], result + args, env)`

        If the program is given as a function, that function is provided the location to
        the virtualenv. If the function returns `None` then venvstarter will
        do nothing more. Otherwise if it will continue as if the program was the result of
        the function all along.

    deps
        An optional list of pip dependencies to install into your virtualenv

    env
        An optional dictionary of environment variables to add to the environment
        that the program is run in.

        Note that each value is formatted with ``venv_parent`` available, which
        is the folder the virtualenv sits in.

    min_python_version
        An int, float, str, tuple or object with "version" of a tuple.

        For example:

        * 3
        * 3.6
        * "3.7.13"
        * (3, 7, 13)
        * distutils.StrictVersion("3.7.13")

        Represents the minimum version of python needed for the virtualenv.

        This will always default to 3.6.

    max_python_version
        An int, float, str, tuple or object with "version" of a tuple.

        For example:

        * 3
        * 3.6
        * "3.7.13"
        * (3, 7, 13)
        * distutils.StrictVersion("3.7.13")

        Represents the maximum version of python allowed for the virtualenv.

        This is optional but when specified must be a version equal to or greater
        than min_python_version.

    Usage::

        Starter(*args, **kwargs).ignite()

    .. note:: you may pass a custom args array into ``ignite`` and it will use
      that instead of sys.argv
    """

    def __init__(
        self,
        program,
        venv_folder,
        venv_folder_name,
        deps=None,
        env=None,
        min_python_version=None,
        max_python_version=None,
    ):
        self.env = env
        self.deps = deps
        self.program = program
        self.venv_folder = venv_folder
        self.venv_folder_name = venv_folder_name
        self.min_python_version = min_python_version
        self.max_python_version = max_python_version

        if self.deps is None:
            self.deps = []

        if self.min_python_version is None:
            self.min_python_version = 3.6

        handler = PythonHandler(self.min_python_version, self.max_python_version)
        self.min_python = handler.min_python
        self.max_python = handler.max_python

        if self.max_python is not None and self.min_python > self.max_python:
            raise Exception("min_python_version must be less than max_python_version")

        if self.min_python < Version(3.6):
            raise Exception("Only support python3.6 and above")

    @memoized_property
    def venv_location(self):
        folder = self.venv_folder
        if folder.is_file():
            folder = folder.parent

        if not folder.exists():
            folder.mkdir()

        return (Path(folder) / self.venv_folder_name).absolute()

    def venv_script(self, name, default=None):
        if os.name == "nt":
            location = self.venv_location / "Scripts" / name
        else:
            location = self.venv_location / "bin" / name

        if location.exists():
            return location

        if os.name == "nt":
            exe = location.with_suffix(".exe")
            if exe.exists():
                return exe

        if default is not None:
            return default

        raise Exception(
            "\n".join(
                [
                    "\nCouldn't find the executable!",
                    f"Wanted {name}",
                    f"Available is {location.iterdir()}",
                ]
            )
        )

    @memoized_property
    def venv_python(self):
        return self.venv_script("python")

    def make_virtualenv(self):
        python_exe = None
        if self.venv_location.exists():
            finder = PythonHandler(self.min_python, self.max_python)
            _, version_info = finder.version_for(self.venv_python)
            if not finder.suitable(version_info):
                # Make sure we can find a suitable python before we remove existing venv
                try:
                    finder.find()
                except Exception as error:
                    raise Exception(
                        f"The current virtualenv has a python that's too old. But can't find a suitable replacement: {error}"
                    )
                else:
                    shutil.rmtree(self.venv_location)

        if not self.venv_location.exists():
            if python_exe is None:
                python_exe = PythonHandler(self.min_python, self.max_python).find()

            print("Creating virtualenv", file=sys.stderr)
            print(f"Destination: {self.venv_location}", file=sys.stderr)
            print(f"Using: {python_exe}", file=sys.stderr)
            print(file=sys.stderr)

            PythonHandler().run_command(
                python_exe,
                f"""
            import venv
            venv.create({json.dumps(str(self.venv_location))}, with_pip=True, symlinks=True)
            """,
            )

            return True

    def install_deps(self):
        deps = []
        for dep in self.deps:
            if "#" in dep:
                deps.append(
                    dict(arg.split("=", 1) for arg in dep.split("#", 1)[1].split("&"))["egg"]
                )
            else:
                deps.append(dep)
        deps = json.dumps(deps)

        # Fix a bug whereby the virtualenv has the wrong sys.executable
        env = dict(os.environ)
        if "__PYVENV_LAUNCHER__" in env:
            del env["__PYVENV_LAUNCHER__"]

        def check_deps():
            handler = PythonHandler()
            question = """
                import pkg_resources
                import sys
                try:
                    pkg_resources.working_set.require({0})
                except (pkg_resources.DistributionNotFound, pkg_resources.VersionConflict) as error:
                    sys.stderr.write(str(error) + "\\n\\n")
                    sys.stderr.flush()
                    raise SystemExit(1)
                """.format(
                deps
            )
            return handler.run_command(self.venv_python, question, check=False).returncode

        ret = check_deps()
        if ret != 0:
            ret = 1
            reqs = None
            try:
                reqs = tempfile.NamedTemporaryFile(
                    delete=False, suffix="venvstarter_requirements", dir="."
                )
                reqs.write("\n".join(str(dep) for dep in self.deps).encode("utf-8"))
                reqs.close()

                cmd = [str(self.venv_python), "-m", "pip", "install", "-r", reqs.name]
                ret = subprocess.call(cmd, env=env)
            finally:
                reqs_loc = Path(reqs.name)
                if reqs is not None and reqs_loc.exists():
                    reqs_loc.unlink()

            if ret != 0:
                raise SystemExit(1)

            ret = check_deps()
            if ret != 0:
                raise Exception("Couldn't install the requirements")

    def determine_command(self, args):
        program = self.program
        if callable(self.program):
            program = self.program(self.venv_location, args)
            if program is None:
                return

        if program is None:
            if args:
                program = list(args)
                args.clear()
            else:
                return

        if isinstance(program, str):
            return [self.venv_script(program)]
        elif isinstance(program, list):
            if program:
                program = [self.venv_script(program[0], default=program[0]), *program[1:]]
            return program
        else:
            raise Exception(f"Not sure what to do with this program: {program}")

    def env_for_program(self):
        env = dict(os.environ)

        home = Path.home()
        venv_parent = self.venv_location.parent
        if self.env is not None:
            normalised = {}

            ev = self.env
            if isinstance(ev, dict):
                ev = [(None, ev)]

            for here, vv in ev:
                for k, v in vv.items():
                    if not isinstance(v, (list, tuple)):
                        normalised[k] = do_format(
                            v, here=str(here), home=str(home), venv_parent=str(venv_parent)
                        )
                    else:
                        normalised[k] = str(
                            Path(
                                *[
                                    do_format(
                                        item,
                                        here=str(here),
                                        home=str(home),
                                        venv_parent=str(venv_parent),
                                    )
                                    for item in v
                                ]
                            )
                        )
            env.update(normalised)

        # Fix a bug whereby the virtualenv has the wrong sys.executable
        if "__PYVENV_LAUNCHER__" in env:
            del env["__PYVENV_LAUNCHER__"]

        return env

    def start_program(self, args):
        if os.environ.get("VENVSTARTER_ONLY_MAKE_VENV") == "1":
            return

        cmd = self.determine_command(args)
        if cmd is None:
            return

        cmd = [*cmd, *(args or ())]

        env = self.env_for_program()

        if os.name == "nt":
            cmd = [str(q) for q in Shebang(*cmd).produce()]
            p = subprocess.run(cmd, env=env)
            sys.exit(p.returncode)

        try:
            os.execve(cmd[0], cmd, env)
        except OSError as error:
            sys.exit(error)

    def run(self, args=None):
        if args is None:
            args = sys.argv[1:]

        made = self.make_virtualenv()

        if made or os.environ.get("VENV_STARTER_CHECK_DEPS", None) != "0":
            self.install_deps()

        self.start_program(args)


class NotSpecified:
    pass


class manager:
    def __init__(self, program, here=None):
        if here is None:
            here = Path(inspect.currentframe().f_back.f_code.co_filename).parent.absolute()

        self.here = here
        self.program = program

        self._env = []
        self._deps = []
        self._max_python = None
        self._min_python = None
        self._venv_folder = NotSpecified
        self._venv_folder_name = None

    def place_venv_in(self, location):
        self._venv_folder = Path(location)
        return self

    def min_python(self, version):
        self._min_python = version
        return self

    def max_python(self, version):
        self._max_python = version
        return self

    def named(self, name):
        self._venv_folder_name = name
        return self

    def add_pypi_deps(self, *deps):
        self._deps.extend(deps)
        return self

    def add_requirements_file(self, *parts):
        home = Path.home()

        path = Path(
            *[
                do_format(
                    part, here=str(self.here), home=str(home), venv_parent=str(self.venv_folder)
                )
                for part in parts
            ]
        )

        if not path.exists():
            raise Exception(
                "Resolved requirements.txt ({parts}) to '{path}' but that does not exist"
            )

        with open(path) as fle:
            for line in fle:
                stripped = line.strip()
                if stripped:
                    self._deps.append(stripped)

        return self

    def add_local_dep(self, *parts, editable=True, version_file=None, with_tests=False, name):
        home = Path.home()

        path = Path(
            *[
                do_format(
                    part, here=str(self.here), home=str(home), venv_parent=str(self.venv_folder)
                )
                for part in parts
            ]
        )

        version = ""
        if version_file is not None:
            if isinstance(version_file, str):
                version_file = [version_file]

            location = Path(path, *version_file)
            version = runpy.run_path(location)["VERSION"]

            if "{version}" not in name:
                raise VersionNotSpecified(name)

        name = do_format(name, version=version)
        if with_tests:
            m = regexes["version_specifier"].match(name)
            if m:
                groups = m.groups()
                name = f"{groups[0]}[tests]{''.join(groups[1:])}"

        dep = f"{Path(path).resolve().absolute().as_uri()}#egg={name}"

        if editable:
            dep = f"-e {dep}"

        self._deps.append(dep)
        return self

    def add_env(self, **env):
        self._env.append((self.here, env))
        return self

    @property
    def venv_folder_name(self):
        if self._venv_folder_name is None:
            if not isinstance(self.program, str) or not regexes["ascii"].match(self.program):
                self._venv_folder_name = ".venv"
            else:
                self._venv_folder_name = f".{self.program}"
        return self._venv_folder_name

    @property
    def venv_folder(self):
        if self._venv_folder is NotSpecified:
            self._venv_folder = self.here
        return self._venv_folder

    def run(self):
        Starter(
            self.program,
            self.venv_folder,
            self.venv_folder_name,
            env=self._env,
            deps=self._deps,
            min_python_version=self._min_python,
            max_python_version=self._max_python,
        ).run()


def ignite(
    venv_folder,
    program,
    deps=None,
    env=None,
    min_python_version=None,
    max_python_version=None,
    venv_folder_name=None,
):
    """
    Convenience function to use venvstarter that remains as a backwards
    compatibility to previous versions of venvstarter. The ``venvstarter.manager``
    should be used instead.

    venv_folder
        A folder that the virtualenv will sit in.

        Note that if you pass in the location of a file, it will use the folder
        that file sits in. This is convenient so you can just pass in __file__
        from your bootstrap script.

    program
        The program to run as None, a list, a string or as a function.

        If set as None, then the python in the virtualenv is run

        If the program is given as a string, we invoke it from the scripts in the
        virtualenv.

        If the program is given as a list, then we `os.execve(result[0], result + args, env)`

        If the program is given as a function, that function is provided the location to
        the python in the virtualenv. If the function returns `None` then venvstarter will
        do nothing more. Otherwise if it will continue as if the program was the result of
        the function all along.

    deps
        An optional list of pip dependencies to install into your virtualenv

    env
        An optional dictionary of environment variables to add to the environment
        that the program is run in.

        Note that each value is formatted with ``venv_parent`` available, which
        is the folder the virtualenv sits in.

    min_python_version
        An int, float, str, tuple or object with "version" of a tuple.

        For example:

        * 3
        * 3.6
        * "3.7.13"
        * (3, 7, 13)
        * distutils.StrictVersion("3.7.13")

        Represents the minimum version of python needed for the virtualenv.

        This will always default to 3.6.

    max_python_version
        An int, float, str, tuple or object with "version" of a tuple.

        For example:

        * 3
        * 3.6
        * "3.7.13"
        * (3, 7, 13)
        * distutils.StrictVersion("3.7.13")

        Represents the maximum version of python allowed for the virtualenv.

        This is optional but when specified must be a version equal to or greater
        than min_python_version.
    """
    m = manager(program).place_venv_in(venv_folder).min_python(min_python_version or "3.6")

    if deps is not None:
        m.add_pypi_deps(*deps).add_env
    if env is not None:
        m.add_env(**env)
    if max_python_version is not None:
        m.max_python(max_python_version)
    if venv_folder_name is not None:
        m.named(venv_folder_name)

    m.run()


__all__ = [
    "manager",
    "PythonHandler",
    "FailedToGetOutput",
    # and ignite for backwards compatibility
    "ignite",
]
