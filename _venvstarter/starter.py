import inspect
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import errors
from . import helpers as hp
from . import python_handler, questions


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
        packaging_version="23.2",
    ):
        self.env = env
        self.deps = deps
        self.program = program
        self.no_binary = no_binary
        self.venv_folder = venv_folder
        self.venv_folder_name = venv_folder_name
        self.packaging_version = packaging_version
        self.min_python_version = min_python_version
        self.max_python_version = max_python_version

        if self.no_binary is None:
            self.no_binary = []

        if self.deps is None:
            self.deps = []

        if self.min_python_version is None:
            self.min_python_version = 3.7

        handler = python_handler.PythonHandler(self.min_python_version, self.max_python_version)
        self.min_python = handler.min_python
        self.max_python = handler.max_python

        if self.max_python is not None and self.min_python > self.max_python:
            raise Exception("min_python_version must be less than max_python_version")

        if self.min_python < python_handler.Version(3.7):
            raise Exception("Only support python3.7 and above")

    @hp.memoized_property
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

        raise errors.ScriptNotFound(location, name)

    @hp.memoized_property
    def venv_python(self):
        return self.venv_script("python")

    def make_virtualenv(self):
        python_exe = None
        if self.venv_location.exists():
            finder = python_handler.PythonHandler(self.min_python, self.max_python)

            try:
                _, version_info = finder.version_for(self.venv_python)
            except errors.ScriptNotFound:
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
                python_exe = python_handler.PythonHandler(self.min_python, self.max_python).find()

            print("Creating virtualenv", file=sys.stderr)
            print(f"Destination: {self.venv_location}", file=sys.stderr)
            print(f"Using: {python_exe}", file=sys.stderr)
            print(file=sys.stderr)

            with_pip = os.name != "nt"

            python_handler.PythonHandler().run_command(
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

        handler = python_handler.PythonHandler()
        question = "\n".join(
            [
                inspect.getsource(questions.determine_if_needs_installation),
                inspect.getsource(questions.ensure_packaging_module),
                f"\ndetermine_if_needs_installation({json.dumps(deps_to_use)}, {json.dumps(no_binary)}, {self.packaging_version})",
            ]
        )
        return handler.run_command(self.venv_python, question, check=False).returncode

    def find_deps_to_be_made_not_binary(self):
        handler = python_handler.PythonHandler()
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
                        normalised[k] = hp.do_format(
                            v, here=str(here), home=str(home), venv_parent=str(venv_parent)
                        )
                    else:
                        normalised[k] = str(
                            Path(
                                *[
                                    hp.do_format(
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

        cmd = [str(q) for q in python_handler.Shebang(*cmd, *(args or ())).produce()]

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
