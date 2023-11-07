import inspect
import re
import runpy
from pathlib import Path

from . import errors
from . import helpers as hp
from . import python_handler, starter

regexes = {
    "ascii": re.compile(r"([a-zA-Z]+(0-9)*)+"),
}


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
        self._packaging_version = None

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

    def set_packaging_version(self, packaging_version):
        """
        This will override the default packaging version installed in the virtualenv for
        python versions from python3.8 and up
        """
        self._packaging_version = packaging_version
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
                hp.do_format(
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
                hp.do_format(
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
                raise errors.VersionNotSpecified(name)

        name = hp.do_format(name, version=version)
        if with_tests:
            m = python_handler.regexes["version_specifier"].match(name)
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
        starter.Starter(
            self.program,
            self.venv_folder,
            self.venv_folder_name,
            env=self._env,
            deps=self._deps,
            no_binary=self._no_binary,
            min_python_version=self._min_python,
            max_python_version=self._max_python,
            **(
                {}
                if self._packaging_version is None
                else {"packaging_version": self._packaging_version}
            ),
        ).run()
