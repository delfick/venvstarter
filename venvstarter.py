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
import pathlib
import sys

here = str(pathlib.Path(__file__).parent.resolve())
if here not in sys.path:
    sys.path.append(here)

from _venvstarter import manager
from _venvstarter.errors import FailedToGetOutput
from _venvstarter.python_handler import PythonHandler, Version
from _venvstarter.starter import Starter
from _venvstarter.version import VERSION


def ignite(*args, **kwargs):
    raise RuntimeError("venvstarter.ignite has been removed, migrate to venvstarter.manager")


__all__ = [
    "manager",
    "VERSION",
    "Version",
    "Starter",
    "PythonHandler",
    "FailedToGetOutput",
]
