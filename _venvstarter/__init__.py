import inspect
import json
import os
import re
import runpy
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from textwrap import dedent

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


class ScriptNotFound(Exception):
    def __init__(self, location, name):
        super().__init__()
        self.name = name
        self.location = location

    def __str__(self):
        available = ", ".join(
            n.name for n in self.location.parent.iterdir() if "." not in n.name and n.exists()
        )
        return "\n".join(
            [
                "\nCouldn't find the executable!",
                f"Wanted {self.name}",
                f"Available is {available}",
            ]
        )


class FailedToGetOutput(Exception):
    def __init__(self, error, stderr):
        super().__init__()
        self.error = error
        self.stderr = stderr

    def __str__(self):
        return f"Failed to get output\nstderr: {self.stderr}\nerror: {self.error}"


class VersionNotSpecified(Exception):
    def __init__(self, name):
        super().__init__()
        self.name = name

    def __str__(self):
        return f"A version_file was specified for a local dependency, but '{{version}}' not found in the name: {self.name}"


class InvalidVersion(Exception):
    def __init__(self, want):
        super().__init__()
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
    The main class that knows how to manage the virtualenv. It is recommended
    that :class:`manager` is used instead of directly using this class.

    venv_folder
        A folder that the virtualenv will sit in.

        Note that if you pass in the location of a file, it will use the folder
        that file sits in. This is convenient so you can just pass in ``__file__``
        from your bootstrap script.

    program
        The program to run as None, a list, a string or as a function.

        If set as None, then the python in the virtualenv is run

        If the program is given as a string, we invoke it from the scripts in the
        virtualenv.

        If the program is given as a list, then we ``os.execve(result[0], result + args, env)``

        If the program is given as a function, that function is provided the location to
        the virtualenv. If the function returns ``None`` then venvstarter will
        do nothing more. Otherwise if it will continue as if the program was the result of
        the function all along.

    deps
        An optional list of pip dependencies to install into your virtualenv

    no_binary
        List of deps that must not be installed as binary. It will identify if
        the dependency has already been installed as a binary and reinstall it
        to be installed from source.

    env
        An optional dictionary of environment variables to add to the environment
        that the program is run in.

        Note that each value is formatted with ``venv_parent`` available, which
        is the folder the virtualenv sits in.

    min_python_version
        An int, float, str, tuple or object with "version" of a tuple.

        For example:

        * 3
        * 3.7
        * "3.7.13"
        * (3, 7, 13)
        * distutils.StrictVersion("3.7.13")

        Represents the minimum version of python needed for the virtualenv.

        This will always default to 3.7.

    max_python_version
        An int, float, str, tuple or object with "version" of a tuple.

        For example:

        * 3
        * 3.7
        * "3.7.13"
        * (3, 7, 13)
        * distutils.StrictVersion("3.7.13")

        Represents the maximum version of python allowed for the virtualenv.

        This is optional but when specified must be a version equal to or greater
        than min_python_version.

    Usage::

        Starter(*args, **kwargs).run()

    .. note:: you may pass a custom args array into ``run`` and it will use
      that instead of sys.argv

    There are also two environment variables that can change what this class does:

    VENVSTARTER_ONLY_MAKE_VENV=1
        This will make the class ensure the virtualenv exists and has the correct
        versions of specified dependencies but will then not do anything with that
        virtualenv

    VENV_STARTER_CHECK_DEPS=0
        This will make the class not check if the dependencies in the virtualenv
        are correct. This increases startup time at the cost of potentially
        having the wrong versions of dependencies in the virtualenv.

    VENVSTARTER_UPGRADE_PIP=0
        This will make sure that pip is not ensured to be greater than 23 before
        requirements are installed
    """

    def __init__(
        self,
        program,
        venv_folder,
        venv_folder_name,
        deps=None,
        no_binary=None,
        env=None,
        min_python_version=None,
        max_python_version=None,
    ):
        self.env = env
        self.deps = deps
        self.program = program
        self.no_binary = no_binary
        self.venv_folder = venv_folder
        self.venv_folder_name = venv_folder_name
        self.min_python_version = min_python_version
        self.max_python_version = max_python_version

        if self.no_binary is None:
            self.no_binary = []

        if self.deps is None:
            self.deps = []

        if self.min_python_version is None:
            self.min_python_version = 3.7

        handler = PythonHandler(self.min_python_version, self.max_python_version)
        self.min_python = handler.min_python
        self.max_python = handler.max_python

        if self.max_python is not None and self.min_python > self.max_python:
            raise Exception("min_python_version must be less than max_python_version")

        if self.min_python < Version(3.7):
            raise Exception("Only support python3.7 and above")

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

        raise ScriptNotFound(location, name)

    @memoized_property
    def venv_python(self):
        return self.venv_script("python")

    def make_virtualenv(self):
        python_exe = None
        if self.venv_location.exists():
            finder = PythonHandler(self.min_python, self.max_python)

            try:
                _, version_info = finder.version_for(self.venv_python)
            except ScriptNotFound:
                version_info = None

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

            with_pip = os.name != "nt"

            PythonHandler().run_command(
                python_exe,
                f"""
            import venv
            venv.create({json.dumps(str(self.venv_location))}, with_pip={with_pip}, symlinks=True)
            """,
            )

            if not with_pip:
                subprocess.run([str(self.venv_python), "-m", "ensurepip"], check=True)

            return True

    def check_deps(self, deps=None, check_no_binary=True):
        deps_to_use = []
        deps = self.deps if deps is None else deps

        for dep in deps:
            if "#" in dep:
                dep = dict(arg.split("=", 1) for arg in dep.split("#", 1)[1].split("&"))["egg"]

            deps_to_use.append(dep)

        no_binary = []
        if check_no_binary:
            no_binary = self.no_binary

        deps = json.dumps(deps_to_use)

        handler = PythonHandler()
        question = """
            import pkg_resources
            import importlib
            import sys

            try:
                pkg_resources.working_set.require({0})
            except (pkg_resources.DistributionNotFound, pkg_resources.VersionConflict) as error:
                sys.stderr.write(str(error) + "\\n\\n")
                sys.stderr.flush()
                raise SystemExit(1)

            for name in {1}:
                if importlib.import_module(name).__file__.endswith(".so"):
                    sys.stderr.write(f"{{name}} needs to not be a binary installation\\n\\n")
                    sys.stderr.flush()
                    raise SystemExit(1)
            """.format(
            deps, no_binary
        )
        return handler.run_command(self.venv_python, question, check=False).returncode

    def find_deps_to_be_made_not_binary(self):
        handler = PythonHandler()
        question = """
            import importlib

            for name in {0}:
                try:
                    if importlib.import_module(name).__file__.endswith(".so"):
                        print(name)
                except ImportError:
                    pass
            """.format(
            json.dumps(self.no_binary)
        )
        found = handler.run_command(self.venv_python, question, get_output=True).split("\n")
        return [shlex.quote(name.strip()) for name in found if name.strip()]

    def install_deps(self, deps=None, check_no_binary=True):
        if deps is None:
            deps = self.deps

        # Fix a bug whereby the virtualenv has the wrong sys.executable
        env = dict(os.environ)
        if "__PYVENV_LAUNCHER__" in env:
            del env["__PYVENV_LAUNCHER__"]

        ret = self.check_deps(deps=deps, check_no_binary=check_no_binary)
        if ret != 0:
            ret = 1
            reqs = None
            try:
                if check_no_binary:
                    to_remove = self.find_deps_to_be_made_not_binary()
                    if to_remove:
                        cmd = [str(self.venv_python), "-m", "pip", "uninstall", "-y", *to_remove]
                        subprocess.call(cmd, env=env)

                reqs = tempfile.NamedTemporaryFile(
                    delete=False, suffix="venvstarter_requirements", dir="."
                )
                for dep in deps:
                    reqs.write(f"\n{dep}".encode("utf-8"))

                if check_no_binary:
                    for dep in self.no_binary:
                        reqs.write(f"\n--no-binary {dep}".encode("utf-8"))

                reqs.close()

                cmd = [str(self.venv_python), "-m", "pip", "install", "-r", reqs.name]
                ret = subprocess.call(cmd, env=env)
            finally:
                if reqs is not None:
                    reqs_loc = Path(reqs.name)
                if reqs is not None and reqs_loc.exists():
                    reqs_loc.unlink()

            if ret != 0:
                raise SystemExit(1)

            ret = self.check_deps(deps=deps, check_no_binary=check_no_binary)
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

        cmd = [str(q) for q in Shebang(*cmd, *(args or ())).produce()]

        env = self.env_for_program()

        if os.name == "nt":
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

        if os.environ.get("VENVSTARTER_UPGRADE_PIP", None) != "0":
            self.install_deps(deps=["pip>=23"], check_no_binary=False)

        if made or os.environ.get("VENV_STARTER_CHECK_DEPS", None) != "0":
            self.install_deps()

        self.start_program(args)


class NotSpecified:
    pass


class manager:
    """
    This is the main entry point to venvstarter. It provides a chained API for
    configuring a venvstarter Starter class and then running it.

    Usage looks like:

    .. code-block:: python

        (__import__("venvstarter").manager("black")
            .add_pypi_deps("black==23.9.1")
            .run()
            )
    """

    def __init__(self, program, here=None):
        """
        See :class:`Starter` for valid values for program.

        ``here`` will default to the absolute path to the directory your script
        lives in.
        """
        if here is None:
            here = Path(inspect.currentframe().f_back.f_code.co_filename).parent.absolute()

        self.here = here
        self.program = program

        self._env = []
        self._deps = []
        self._no_binary = []
        self._max_python = None
        self._min_python = None
        self._venv_folder = NotSpecified
        self._venv_folder_name = None

    def place_venv_in(self, location):
        """
        This will configure the virtualenv to exist in the provided location.
        """
        self._venv_folder = Path(location)
        return self

    def min_python(self, version):
        """
        This will set the minimum version of python as provided. See :class:`Starter`
        """
        self._min_python = version
        return self

    def max_python(self, version):
        """
        This will set the maximum version of python as provided. See :class:`Starter`
        """
        self._max_python = version
        return self

    def named(self, name):
        """
        This will set the name of the virtualenv folder
        """
        self._venv_folder_name = name
        return self

    def add_pypi_deps(self, *deps):
        """
        This will add to the list of dependencies from pypi. This method may
        be called multiple times to add many dependencies.
        """
        self._deps.extend(deps)
        return self

    def add_no_binary(self, *no_binary):
        """
        This will register more dependencies that must be installed from source.
        See :class:`Starter`.
        """
        self._no_binary.extend(no_binary)
        return self

    def add_requirements_file(self, *parts):
        """
        This adds a single requirements file. The strings you provide will be
        joined together to form one path. Each string will be formatted with:

        here
            The location of the directory your script exists in

        home
            The location of your current user's home folder

        venv_parent
            The location of the folder the virtualenv will sit in.


        For example:

        .. code-block:: python

            manager(...).add_requirements_file("{here}", "..", "requirements.txt")
        """
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
        """
        Adds a dependency that is local to your script. The path to where a
        folder where a ``setup.py`` can be found is provided as parts of a file
        that are joined together. Formatted into each part is ``here``, ``home``
        and ``venv_parent`` just like the parts in :meth:`add_requirements_file`.

        editable
            This is the same as saying ``pip install -e {path}``. This is how
            pip is told to install the dependency as a symlink rather than as
            a static copy of the code at the time of installation.

        version_file
            This needs to be a tuple of strings. These are joined as a path from
            the source code of your dependency. This must be a file containing
            a variable called ``VERSION`` that is a version number for the
            dependency. Venvstarter will reinstall the local dependency if this
            number changes, which allows any new sub dependencies to be found.

        with_tests
            This is equivalent to saying ``pip install "{path}[tests]"`` and
            will tell pip to also install any dependencies found in the ``tests``
            section of the ``extra_requires`` in setup.py.

        name
            This is used to tell pip the name of the dependency that is installed
            from this location.
        """
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
        """
        Updates the dictionary of environment variables to run the program with
        """
        self._env.append((self.here, env))
        return self

    @property
    def venv_folder_name(self):
        """
        Returns the name of the virtualenv folder.

        If it has been explicitly set, then that value is returned. Otherwise if
        the program is a string then it is returned with a prefixed dot, otherwise
        it uses ``.venv``.
        """
        if self._venv_folder_name is None:
            if not isinstance(self.program, str) or not regexes["ascii"].match(self.program):
                self._venv_folder_name = ".venv"
            else:
                self._venv_folder_name = f".{self.program}"
        return self._venv_folder_name

    @property
    def venv_folder(self):
        """
        The folder the virtualenv will sit in. If this has explicitly set, then
        that is returned, otherwise the value for ``here`` is returned.
        """
        if self._venv_folder is NotSpecified:
            self._venv_folder = self.here
        return self._venv_folder

    def run(self):
        """
        This creates the :class:`Starter` instance with the specified
        configuration and calls run on that.
        """
        Starter(
            self.program,
            self.venv_folder,
            self.venv_folder_name,
            env=self._env,
            deps=self._deps,
            no_binary=self._no_binary,
            min_python_version=self._min_python,
            max_python_version=self._max_python,
        ).run()


__all__ = [
    "manager",
    "PythonHandler",
    "FailedToGetOutput",
]
