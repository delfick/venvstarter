.. _features:

Features
========

``venvstarter`` provides a range of features for controlling how dependencies are
managed and how the resulting ``virtualenv`` is used when the script is run.

.. note:: This page will speak about ``venvstarter`` in terms of the :class:`venvstarter.manager`
   class as that's the intended way to use this library. This class is a wrapper
   around the core logic provided by :class:`venvstarter.Starter`.

All the features lead to this pattern when a script that uses ``venvstarter`` is run:

.. code-block:: rst

    1. Create virtualenv if it doesn't exist
    2. Install dependencies if the existing dependencies in the virtualenv don't match
    3. os.exec into something from the virtualenv

.. _simple_venvstarter_python:

Creating an isolated Python to use
----------------------------------

``venvstarter`` is used to create an executable that will run something from a
``virtualenv``. Sometimes all that is wanted is the python binary in that ``virtualenv``
and for this purpose, ``None`` may be specified:

/my_python

    .. code-block:: python

        #!/usr/bin/env python

        # Instantiating the manager with None tells venvstarter to use the Python binary
        manager = __import__("venvstarter").manager(None)

        # optionally specify a desired range of python versions
        manager.min_python("3.10")
        # with any dependencies in the venv as per the API on the manager

        # And run creates and runs the desired program in the virtualenv
        manager.run()

And then::

    > chmod +x ./my_python
    > ./my_python /path/to/some/python/script.py

Will run the ``script.py`` using a fresh python3.10 as found in that ``virtualenv``.

.. note:: When the manager is instantiated with a program that is not a string
   (i.e. ``None`` or a callable object) then the ``virtualenv`` will default to being
   called ``.venv``. There is the ``manager.named(".my_venv")`` method to override
   that default.

.. _simple_venvstarter_tool:

Using ``venvstarter`` to run a python tool
------------------------------------------

Let's say the desire is to run the ``black`` auto formatter without requiring the
user or CI system to have a particular version installed:

/format

    .. code-block:: python

        #!/usr/bin/env python

        # Instantiating the manager with "black" tells venvstarter to use the
        # "black" console script that gets created by installing black
        manager = __import__("venvstarter").manager("black")

        # instruct venvstarter to ensure black exists at a particular version
        # These are essentially lines in a requirements.txt file
        manager.add_pypi_deps("black===22.6.0")

        # And run creates and runs the desired program in the virtualenv
        manager.run()

And then::

    > chmod +x ./format
    > ./format path/to/code

Will ensure there is a ``.black`` folder next to ``format`` that contains a
``virtualenv`` that contains ``black`` from ``pypi`` at version ``22.6.0`` and then
run ``./.black/bin/black path/to/code``.

.. _program_as_a_function:

Dynamically choosing what to run
--------------------------------

It's possible to make ``venvstarter`` run something different depending on what
arguments are provided on the CLI.

/my_program

    .. code-block:: python
        
        #!/usr/bin/env python3

        from pathlib import Path
        import typing as tp

        def run(venv_location: Path, args: list[str]) -> tp.Optional[str | list[str]]:
            if args and args[0] == "one":
                args.pop(0)
                return "command-one"
            elif args and args[0] == "two":
                args.pop(0)
                return "command-two"
            else:
                return "command-three"

        # Optionally specified the name of the virtualenv is .runner
        # The manager is initiated with a callable and so venvstarter would otherwise
        # default to naming the virtualenv ".venv"
        manager = __import__("venvstarter").manager(run).named(".runner")
        manager.run()

and then::

    > chmod +x ./my_program

    # Equivalent to > command-one 1 2 3
    > ./my_program one 1 2 3

    # Equivalent to > command-two 4 5 6
    > ./my_program two 4 5 6

    # Equivalent to > command-three three 7 8 9
    > ./my_program three 7 8 9

In this case the manager has been instantiated with a function that takes in a
standard library ``Path`` object pointing to where the ``virtualenv`` env is, and
the list of arguments from the command line.

The function must return ``None``, a single string, or a list of strings.

Returning ``None`` means ``venvstarter`` will execute the python binary in the ``virtualenv``.
Returning a single string will make it use that name to find that executable
in the ``virtualenv``. Returning a list of strings will use the first string as the
executable and extra arguments before appending the strings that remain in the
``args`` list that was passed in.

.. note:: The ``args`` list passed into the function can be modified in place to
   affect what ``venvstarter`` uses with the specified command.

.. _venstarter_behaviour_env:

Environment variables to change behavior
----------------------------------------

There are a couple environment variables that change what ``venvstarter`` does:

``VENV_STARTER_CHECK_DEPS=0``
    When this is set to 0 then ``venvstarter`` will not check if the dependencies in
    the ``virtualenv`` are correct if the ``virtualenv`` already exists. This speeds up
    startup time as checking dependencies takes a second or two.


``VENVSTARTER_ONLY_MAKE_VENV=1``
    When this is set to 1 then ``venvstarter`` will ensure the ``virtualenv`` exists and
    has correct dependencies and then exit before doing anything with the
    ``virtualenv``.

``VENVSTARTER_UPGRADE_PIP=0``
    This will make sure that pip is not ensured to be greater than 23 before
    requirements are installed

.. _local_deps:

Installing local dependencies
-----------------------------

``venvstarter`` has the ability to install a local dependency as a symlink in the
``virtualenv`` and only reinstall that dependency if it's version changes. This is
how ``venvstarter`` knows to change any sub dependencies that come from that code.

For example, if there is this code structure in the repository::

    /
      pyproject.toml
      mycode/
        __init__.py
        executor.py
      run

/pyproject.toml

.. code-block:: toml

    [build-system]
    requires = ["hatchling"]
    build-backend = "hatchling.build"

    [project]
    name = "mycode"
    dynamic = ["version"]
    dependencies = [
        "dict2xml==1.7.0"
    ]

    [project.scripts]
    take-over-the-world = "mycode.executor:main"

    [tool.hatch.version]
    path = "mycode/__init__.py"

    [tool.hatch.build.targets.sdist]
    include = [
        "/mycode"
    ]

/mycode/__init__.py

.. code-block:: python

    VERSION = "0.1"

/mycode/executor.py

.. code-block:: python

    def main():
        print("The world is ours!")

/run

    .. code-block:: python
        
        #!/usr/bin/env python3

        manager = __import__("venvstarter").manager("take-over-the-world").named(".runner")
        manager.add_local_dep(
            "{here}",
            version_file=(
                "mycode",
                "__init__.py",
            ),
            name="mycode=={version}",
            with_tests=True,
        )
        manager.run()

This says that the ``setup.py`` to look for is in the same folder as the ``venvstarter``
script (the ``{here}`` gets formatted with the folder the script is in) and that
relative to where the ``setup.py`` file is a ``VERSION`` variable can be found in
``mycode/__init__.py``. The dependency needs a name so that ``venvstarter`` knows
what to check when ``run`` is executed in the future and so ``mycode=={version}``
is provided, which gets formatted with the value of that ``VERSION`` variable.

The ``with_tests`` then adds any ``tests`` extra requires block, which is
equivalent to saying::

    > python install -e ".[tests]"

The full API can be found at :meth:`venvstarter.manager.add_local_dep`

Now upon running ``./run`` it will print "The world is ours!" to the console
as it will execute the ``take-over-the-world`` console script installed by the
dependency, which runs ``mycode.executor.main``.

.. _external_deps:

Installing from a requirements file
-----------------------------------

The manager also has the ability to find dependencies from a ``requirements.txt``: 

.. code-block:: python

    #!/usr/bin/env python3

    manager = __import__("venvstarter").manager(None)
    manager.add_requirements_file("{here}", "requirements.txt")
    manager.run()

The ``add_requirements_file`` method takes in multiple strings that are joined
together as a path (so the difference between slashes in ``linux`` and windows do
not have to be considered) and will format each string with:

``here``
    The location of the directory this script exists in

``home``
    The location of the current user's home folder

``venv_parent``
    The location of the folder the ``virtualenv`` will sit in.

.. note:: Every time ``add_pypi_deps`` is called, each argument supplied to
   the method is its own line in a requirements.txt that is installed with pip.

.. _install_source_only:

Installing dependencies from source only
----------------------------------------

Sometimes it's desirable to not use a binary wheel for a dependency. This can be
specified using ``add_no_binary`` which takes the names of dependencies to install
from source:

.. code-block:: python

    manager = __import__("venvstarter").manager("black")
    manager.add_pypi_deps("noseOfYeti[black]>=2.4.2")
    manager.add_no_binary("black")
    manager.run()

Here ``black`` is installed from source because ``noy-black`` requires it be
installed from source, so it can add some stuff on top of it.

This is equivalent to::

    > python -m pip install --no-binary black noy-black noseOfYeti

.. _when_new_python:

When a new python version is needed
-----------------------------------

When a ``venvstarter`` script is run, it will check:

* Does ``virtualenv`` exist?
* Is it the desired python?
* Are the specified dependencies at the desired versions?

The version of python is controlled via :meth:`venvstarter.manager.min_python`
and :meth:`venvstarter.manager.max_python`.

For example:

.. code-block:: python

    manager = __import__("venvstarter").manager(None)
    manager.min_python("3.7")
    manager.max_python("3.11")
    manager.run()

With this script ``venvstarter`` will stop when it finds a suitable python:

* Is there ``python3.11`` on PATH?
* Is there ``python3.10``
* Is there ``python3.9``
* Is there ``python3.8``
* Is there ``python3.7``
* Is ``python3`` in PATH within the range?
* Is ``python`` in PATH within the range?

For all of these, it determines if it's a valid python at that version by
effectively executing ``print(sys.version_info)`` with that binary.

When ``venvstarter`` finds an existing ``virtualenv`` it will use the python in that
``virtualenv`` to do the same check and will delete the ``virtualenv`` if the python
is not a suitable version and a suitable version can be found on the system so
that it may recreate the ``virtualenv``.

.. _works_on_windows:

Works on Windows as well
------------------------

``venvstarter`` has support for windows where the layout of the ``virtualenv`` is slightly
different and there are some different semantics around open files.

The tests for ``venvstarter`` are also run in a Windows environment for every change
that is made to this program.

.. _lockfiles:

Are there lock files? (nope, sorry)
-----------------------------------

The last time I investigated whether I could use new dependency management systems
like Poetry as a library, I quickly found that wasn't possible. So for now
``venvstarter`` continues to use pip (which also means ``venvstarter`` has no external
dependencies of its own) and pip itself does not support ``lockfiles``.

.. _boostrapping_venvstarter:

Bootstrapping ``venvstarter``
-----------------------------

``venvstarter`` means that a programmer can easily create an isolated environment
for any program desired to be run, however it does require the system has
``venvstarter`` itself installed. To remove this step for non-technical users it
can be useful to have a small script that ensures ``venvstarter`` is installed
without manual intervention.

An example of this can be found in the ``venvstarter`` repo itself!

* https://github.com/delfick/venvstarter/blob/main/tools/example_bootstrap_venvstarter.py

This is used by the two scripts in that folder that are used to run format
and lint tools in CI (and locally for anyone who doesn't have that setup in
their editor)

* https://github.com/delfick/venvstarter/blob/main/tools/black
* https://github.com/delfick/venvstarter/blob/main/tools/pylama

Usage is using ``runpy`` to execute that script (more reliable than tricks to ensure
the import PATH is correct) and then importing ``venvstarter`` will work.

The script works by using the fact that the standard library ``importlib.reload``
can be used to find a dependency if it's been pip installed after a failed import.
