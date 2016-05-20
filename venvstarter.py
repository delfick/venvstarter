"""
A program to manage your program in a virtualenv and ensure it and any other
dependencies you may have are in that virtualenv before starting the program.

Essentially you create a bootstrap script using this program, something like::

    #!/usr/bin/env python
    __requires__ = ["venvstarter"]
    import pkg_resources

    from venvstarter import ignite
    ignite(__file__, "harpoon"
        , deps = ["docker-harpoon==0.6.8.3"]
        , env = {"HARPOON_CONFIG": "{venv_parent}/harpoon.yml"}
        )

The __requires__ at the top is so that pkg_resources can tell you if
``venvstarter`` is not installed, and then we import ``venvstarter.ignite`` and
use that to run the ``harpoon`` program after first ensuring we have a virtualenv
called ``.harpoon`` in the same folder as this bootstrap script along with
the correct version of harpoon.

As a bonus we can also set environment variables that have ``venv_parent``
formatted into them which is the folder that the virtualenv sits in.

So your folder structure would look something like::

    /project
        bootstrap
        .harpoon/
        harpoon.yml

Slow Startup
    There is only one disadvantage and that is this process adds about 0.6 seconds
    to your startup time for your application.

    The reason for this is because we have to shell out to the python in the
    virtualenv to work out if we need to update any of the dependencies.

    If you want to skip checking the versions of your dependencies, then set
    VENV_STARTER_CHECK_DEPS=0 in your environment before starting the bootstrap
    and then the delay goes down to about 0.2 seconds.
"""
from distutils.version import StrictVersion
from textwrap import dedent
import pkg_resources
import subprocess
import tempfile
import shlex
import json
import pip
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

class Starter(object):
    """
    The main class that knows how to manage the virtualenv

    venv_folder
        A folder that the virtualenv will sit in.

        Note that if you pass in the location of a file, it will use the folder
        that file sits in. This is convenient so you can just pass in __file__
        from your bootstrap script.

    program
        The name of the program in the virtualenv's ``bin`` directory to invoke.

        venvstarter will do a ``os.exec`` to this program as it's last action.

    deps
        An optional list of pip dependencies to install into your virtualenv

    env
        An optional dictionary of environment variables to add to the environment
        that the program is run in.

        Note that each value is formatted with ``venv_parent`` available, which
        is the folder the virtualenv sits in.

    min_python_version
        Either a string or a pkg_resources.StrictVersion instance representing
        the minimum version of python needed for the virtualenv.

        This will always default to 3.5.

    max_python_version
        An optional string or a pkg_resources.StrictVersion instance representing
        the maximum version of python needed for the virtualenv.

        This must be a version equal to or greater than min_python_version.

    Usage::

        Starter(*args, **kwargs).ignite()

    .. note:: you may pass a custom args array into ``ignite`` and it will use
      that instead of sys.argv
    """
    def __init__(self, venv_folder, program, deps=None, env=None, min_python_version=3.5, max_python_version=None):
        self.env = env
        self.deps = deps
        self.program = program
        self.venv_folder = venv_folder
        self.min_python_version = min_python_version
        self.max_python_version = max_python_version

        if self.max_python is not None and self.min_python > self.max_python:
            raise Exception("min_python_version must be less than max_python_version")

    @memoized_property
    def min_python(self):
        if self.min_python_version is None:
            return StrictVersion("3.5")
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
        return os.path.abspath(os.path.join(folder, ".{0}".format(self.program)))

    @memoized_property
    def program_location(self):
        return os.path.join(self.venv_location, "bin", self.program)

    @memoized_property
    def pip_location(self):
        return os.path.join(self.venv_location, "bin", "pip")

    @memoized_property
    def venv_python(self):
        return os.path.join(self.venv_location, "bin", "python")

    @memoized_property
    def python_location(self):
        def suitable(version):
            if version == self.min_python:
                return True

            if version < self.min_python:
                return False

            if self.max_python is None:
                return True

            if version > self.max_python:
                return False

        this_python = sys.executable
        this_python_version = StrictVersion("{0}.{1}.{2}".format(*sys.version_info))
        if suitable(this_python_version):
            return this_python

        question = """{0} -c 'import sys, json; print(json.dumps(list(sys.version_info)))'"""
        version_info = lambda exe: subprocess.check_output(shlex.split(question.format(exe))).strip()
        version_question = lambda exe: StrictVersion("{0}.{1}.{2}".format(*json.loads(version_info(exe))))

        def is_suitable_python(location):
            try:
                found_python = subprocess.check_output(["which", location])
            except subprocess.CalledProcessError:
                return None

            found_python_version = version_question(found_python)
            if suitable(found_python_version):
                return found_python

        ret = is_suitable_python("python")
        if ret: return ret

        ret = is_suitable_python("python{0}.{1}".format(*self.min_python.version))
        if ret: return ret

        ret = is_suitable_python("python{0}".format(*self.min_python.version))
        if ret: return ret

        raise Exception("Couldn't find a suitable python!")

    def make_virtualenv(self):
        if not os.path.exists(self.venv_location):
            res = os.system("virtualenv {0} -p {1}".format(self.venv_location, self.python_location))
            if res != 0:
                raise Exception("Failed to make the virtualenv!")
            return True

    def install_deps(self):
        question = dedent("""\
            import pkg_resources
            import sys
            try:
                pkg_resources.working_set.require({0})
            except (pkg_resources.DistributionNotFound, pkg_resources.VersionConflict) as error:
                sys.stderr.write(str(error) + "\\n\\n")
                sys.stderr.flush()
                raise SystemExit(1)
        """.format(json.dumps(list(str(dep) for dep in self.deps))))

        ret = os.system("{0} -c '{1}'".format(self.venv_python, question))
        if ret != 0:
            with tempfile.NamedTemporaryFile(delete=True, dir=".") as reqs:
                reqs.write("\n".join(str(dep) for dep in self.deps))
                reqs.flush()
                ret = os.system("{0} install -r {1}".format(self.pip_location, reqs.name))
                if ret != 0:
                    raise SystemExit(1)

        ret = os.system("{0} -c '{1}'".format(self.venv_python, question))
        if ret != 0:
            raise Exception("Couldn't install the requirements")

    def start_program(self, args):
        env = dict(os.environ)
        venv_parent = os.path.dirname(self.venv_folder)
        if self.env is not None:
            env.update(dict((k, v.format(venv_parent=venv_parent)) for k, v in self.env.items()))

        try:
            os.execve(self.program_location, [self.program_location] + args, env)
        except OSError:
            print("Sorry!!!! Couldn't find {0}".format(self.program_location))
            raise SystemExit(1)

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

