"""
A program to manage your program in a virtualenv and ensure it and any other
dependencies you may have are in that virtualenv before starting the program.

It allows the creation of a shell script like the following::

    #!/usr/bin/env python3

    (
        __import__("venvstarter").manager
        .named(".harpoon")
        .add_pypi_deps("docker-harpoon==0.12.1")
        .add_env(HARPOON_CONFIG="{venv_parent}/harpoon.yml")
        .run("harpoon")
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
from distutils.version import StrictVersion
from textwrap import dedent
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

VERSION = "0.8.1"


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


class PythonFinder:
    def __init__(self, min_python, max_python):
        self.min_python = min_python
        self.max_python = max_python

    def suitable(self, version):
        if version is None:
            return False

        if version < self.min_python:
            return False

        if self.max_python is not None and version > self.max_python:
            return False

        return True

    def version_for(self, executable):
        if executable is None:
            return None, None

        question = [
            executable,
            "-c",
            "import sys, json; print(json.dumps(list(sys.version_info)))",
        ]

        try:
            version_info = subprocess.check_output(question).strip().decode()
        except subprocess.CalledProcessError:
            return executable, None
        else:
            return executable, StrictVersion("{0}.{1}.{2}".format(*json.loads(version_info)))

    def versions(self, starting):
        version = starting
        while version < self.min_python:
            if version.version[1] > self.min_python.version[1]:
                version = StrictVersion(f"{version.version[0]+1}")
            else:
                version = StrictVersion(f"{version.version[0]+1}.{version.version[1]}")

        while version >= self.min_python:
            yield "python{0}.{1}".format(*version.version)

            if version.version[1] == 0:
                if version.version[0] == 0:
                    break

                version = StrictVersion(f"{version.version[0]-1}.{0}")
            else:
                version = StrictVersion(f"{version.version[0]}.{version.version[1]-1}")

        version = starting
        while version >= self.min_python:
            yield "python{0}".format(*version.version)

            if version.version[0] <= 3:
                break

            version = StrictVersion(f"{version.version[0] - 1}")

    def find(self):
        max_python = self.min_python
        if self.max_python is None:
            _, max_python_1 = self.version_for(shutil.which("python3"))
            _, max_python_2 = self.version_for(shutil.which("python"))
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
            executable, found = self.version_for(shutil.which(version))
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
        An optional string or a distutils.version.StrictVersion instance
        representing the minimum version of python needed for the virtualenv.

        This will always default to 3.6.

    max_python_version
        An optional string or a distutils.version.StrictVersion instance
        representing the maximum version of python needed for the virtualenv.

        This must be a version equal to or greater than min_python_version.

    Usage::

        Starter(*args, **kwargs).ignite()

    .. note:: you may pass a custom args array into ``ignite`` and it will use
      that instead of sys.argv
    """

    def __init__(
        self,
        venv_folder,
        program,
        deps=None,
        env=None,
        min_python_version=None,
        max_python_version=None,
        venv_folder_name=None,
    ):
        self.env = env
        self.deps = deps
        self.program = program
        self.venv_folder = venv_folder
        self.min_python_version = min_python_version
        self.max_python_version = max_python_version

        if self.deps is None:
            self.deps = []

        if venv_folder_name is None:
            if not isinstance(program, str) or not re.match("([a-zA-Z]+(0-9)*)+", program):
                venv_folder_name = ".venv"
            else:
                venv_folder_name = f".{self.program}"
        self.venv_folder_name = venv_folder_name

        if self.min_python_version is None:
            self.min_python_version = 3.0

        if self.max_python is not None and not isinstance(self.max_python, StrictVersion):
            self.max_python = StrictVersion(str(self.max_python))
        if not isinstance(self.min_python, StrictVersion):
            self.min_python = StrictVersion(str(self.min_python))

        if self.max_python is not None and self.min_python > self.max_python:
            raise Exception("min_python_version must be less than max_python_version")

        if self.min_python_version < 3:
            raise Exception("Only support python3 and above")

    @memoized_property
    def min_python(self):
        if self.min_python_version is None:
            return StrictVersion("3.6")
        elif isinstance(self.min_python_version, StrictVersion):
            return self.min_python_version
        else:
            return StrictVersion(str(self.min_python_version))

    @memoized_property
    def max_python(self):
        if self.max_python_version is None:
            return None
        elif isinstance(self.max_python_version, StrictVersion):
            return self.max_python_version
        else:
            return StrictVersion(str(self.max_python_version))

    @memoized_property
    def venv_location(self):
        folder = self.venv_folder
        if os.path.isfile(folder):
            folder = os.path.dirname(folder)

        if not os.path.exists(folder):
            os.makedirs(folder)

        return os.path.abspath(os.path.join(folder, self.venv_folder_name))

    def venv_script(self, name):
        if os.name == "nt":
            return os.path.join(self.venv_location, "Scripts", name)
        else:
            return os.path.join(self.venv_location, "bin", name)

    @memoized_property
    def venv_python(self):
        return self.venv_script("python")

    def make_virtualenv(self):
        python_exe = None
        if os.path.exists(self.venv_location):
            finder = PythonFinder(self.min_python, self.max_python)
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

        if not os.path.exists(self.venv_location):
            if python_exe is None:
                python_exe = PythonFinder(self.min_python, self.max_python).find()

            print("Creating virtualenv")
            print(f"Destination: {self.venv_location}")
            print(f"Using: {python_exe}")
            print()

            res = os.system(
                " ".join(
                    shlex.quote(s)
                    for s in (
                        python_exe,
                        "-c",
                        f'__import__("venv").create("{self.venv_location}", with_pip=True)',
                    )
                )
            )
            if res != 0:
                raise Exception("Failed to make the virtualenv!")
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
            question = dedent(
                """\
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
            )

            return subprocess.call([self.venv_python, "-c", question])

        ret = check_deps()
        if ret != 0:
            with tempfile.NamedTemporaryFile(delete=True, dir=".") as reqs:
                reqs.write("\n".join(str(dep) for dep in self.deps).encode("utf-8"))
                reqs.flush()

                cmd = [self.venv_python, "-m", "pip", "install", "-r", reqs.name]
                ret = subprocess.call(cmd, env=env)

                if ret != 0:
                    raise SystemExit(1)

            ret = check_deps()
            if ret != 0:
                raise Exception("Couldn't install the requirements")

    def determine_command(self):
        program = self.program
        if callable(self.program):
            program = self.program(self.venv_python)
            if program is None:
                return

        if program is None:
            return [self.venv_python]
        elif isinstance(program, str):
            return [self.venv_script(program)]
        elif isinstance(program, list):
            return program
        else:
            raise Exception(f"Not sure what to do with this program: {program}")

    def start_program(self, args):
        if os.environ.get("VENVSTARTER_ONLY_MAKE_VENV") == "1":
            return
        env = dict(os.environ)
        venv_parent = os.path.dirname(self.venv_location)
        if self.env is not None:
            env.update({k: v.format(venv_parent=venv_parent) for k, v in self.env.items()})

        # Fix a bug whereby the virtualenv has the wrong sys.executable
        if "__PYVENV_LAUNCHER__" in env:
            del env["__PYVENV_LAUNCHER__"]

        cmd = self.determine_command()
        if not cmd:
            return

        try:
            os.execve(cmd[0], cmd + args, env)
        except OSError as error:
            sys.exit(error)

    def ignite(self, args=None):
        """
        * Make the virtualenv
        * Install dependencies into that virtualenv
        * Start the program!
        """
        if args is None:
            args = sys.argv[1:]

        made = self.make_virtualenv()

        if made or os.environ.get("VENV_STARTER_CHECK_DEPS", None) != "0":
            self.install_deps()

        self.start_program(args)


class NotSpecified:
    pass


class VenvManager:
    def __init__(self):
        self._env = {}
        self._deps = []
        self._max_python = None
        self._min_python = None
        self._venv_folder = NotSpecified
        self._venv_folder_name = None

    def place_venv_in(self, location):
        self._venv_folder = location
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

    def add_local_dep(self, *parts, version_file=None, with_tests=False, name):
        home = os.path.expanduser("~")
        here = os.path.abspath(os.path.dirname(inspect.currentframe().f_back.f_code.co_filename))

        path = os.path.join(*[part.format(here=here, home=home) for part in parts])

        version = ""
        if version_file is not None:
            if isinstance(version_file, str):
                version_file = [version_file]
            version_file = os.path.join(path, *version_file)
            version = runpy.run_path(version_file)["VERSION"]

        name = name.format(version=version)
        if with_tests:
            groups = re.match("([^=><]+)(.*)", name).groups()
            name = f"{groups[0]}[tests]{''.join(groups[1:])}"

        self._deps.append(f"file://{path}#egg={name}")
        return self

    def add_env(self, **env):
        self._env.update(env)
        return self

    def run(self, program=None):
        if self._venv_folder is NotSpecified:
            self._venv_folder = os.path.abspath(
                os.path.dirname(inspect.currentframe().f_back.f_code.co_filename)
            )

        Starter(
            self._venv_folder,
            program,
            env=self._env,
            deps=self._deps,
            venv_folder_name=self._venv_folder_name,
            min_python_version=self._min_python,
            max_python_version=self._max_python,
        ).ignite()


# An instance for use in single run scripts
manager = VenvManager()


def ignite(*args, **kwargs):
    """
    Convenience function to create a Starter instance and call ignite on it

    This remains as a backwards compatibility to previous versions of
    venvstarter
    """
    Starter(*args, **kwargs).ignite()


__all__ = ["ignite", "manager", "VenvManager", "PythonFinder", "Starter"]
