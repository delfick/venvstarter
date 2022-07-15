.. _features:

Features
========

Venvstarter provides a range of features for controlling how dependencies are
managed and how the resulting virtualenv is used when the script is run.

.. note:: This page will speak about venvstarter in terms of the :class:`venvstarter.manager`
   class as that's the intended way to use this library. This class is a wrapper
   around the core logic provided by :class:`venvstarter.Starter`.

All the features lead to this pattern when you run a script that uses venvstarter:

.. code-block:: rst

    1. Create virtualenv if it doesn't exist
    2. Install dependencies if the existing dependencies in the virtualenv don't match
    3. os.exec into something from the virtualenv

.. _simple_venvstarter_python:

Creating an isolated Python to use
----------------------------------

.. _simple_venvstarter_tool:

Using venvstarter to run a python tool
--------------------------------------

.. _program_as_a_function:

Dynamically choosing what to run
--------------------------------

.. _venstarter_behaviour_env:

Environment variables to change behaviour
-----------------------------------------

.. _install_source_only:

Installing dependencies from source only
----------------------------------------

.. _external_deps:

Installing from a requirements file and pypi
--------------------------------------------

.. _local_deps:

Installing local dependencies
-----------------------------

.. _when_new_python:

When a new python version is needed
-----------------------------------

.. _works_on_windows:

Works on windows as well
------------------------

.. _lockfiles:

Are there lock files? (nope, sorry)
-----------------------------------

.. _boostrapping_venvstarter:

Bootstrapping Venvstarter
-------------------------
