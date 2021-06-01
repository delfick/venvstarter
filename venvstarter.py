"""
A program to manage your program in a virtualenv and ensure it and any other
dependencies you may have are in that virtualenv before starting the program.

Essentially you create a bootstrap script using this program, something like::

    #!/usr/bin/env python3

    from venvstarter import ignite
    ignite(__file__, "harpoon"
        , deps = ["docker-harpoon==0.12.1"]
        , env = {"HARPOON_CONFIG": "{venv_parent}/harpoon.yml"}
        )

First we import ``venvstarter.ignite`` and use that to run the ``harpoon``
program after first ensuring we have a virtualenv called ``.harpoon`` in the
same folder as this bootstrap script along with the correct version of harpoon.

As a bonus we can also set environment variables that have ``venv_parent``
formatted into them which is the folder that the virtualenv sits in.

So your folder structure would look something like::

    /project
        bootstrap
        .harpoon/
        harpoon.yml

Slow Startup
    There is only one disadvantage and that is this process adds about 0.4 seconds
    to your startup time for your application.

    The reason for this is because we have to shell out to the python in the
    virtualenv to work out if we need to update any of the dependencies. And the
    way I determine if packages has changed relies on importing pkg_resources,
    which is very slow.

    If you want to skip checking the versions of your dependencies, then set
    VENV_STARTER_CHECK_DEPS=0 in your environment before starting the bootstrap
    and then the delay goes down to about 0.1 seconds.
"""
from distutils.version import StrictVersion
from textwrap import dedent
import subprocess
import tempfile
import shutil
import shlex
import json
import sys
import os


class memoized_property(object):
    """Just to make sure we don't call os.path things more often than we need to"""

    def __init__(self, func):
        self.func = func
        self.key = ".{0}".format(self.func.__name__)

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

    def version_for(self, name):
        executable = shutil.which(name)
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
            _, max_python_1 = self.version_for("python3")
            _, max_python_2 = self.version_for("python")
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
            executable, found = self.version_for(version)
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

        if venv_folder_name is None:
            venv_folder_name = f".{self.program}"
        self.venv_folder_name = venv_folder_name

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
        if not os.path.exists(self.venv_location):
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


def ignite(*args, **kwargs):
    """Convenience function to create a Starter instance and call ignite on it"""
    Starter(*args, **kwargs).ignite()
