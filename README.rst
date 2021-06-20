Venvstarter
===========

Program to bootstrap a virtualenv for your program!

Full documentation at http://venvstarter.readthedocs.io

Installation
------------

Venvstarter is python3 only and I recommend installing using pip::

    $ python3 -m pip install venvstarter

Why
---

I used to manage this kind of bootstrap script with bash, similar to how I
manage the virtualenv for the documentation for this project.

The problem with that approach is it becomes difficult to enforce particular
versions of python and, in particular, multiple dependencies in a way that
doesn't involve some pretty horrible code. So I made this :)

Api
---

.. automodule:: venvstarter

.. autoclass:: venvstarter.Starter

.. autofunction:: venvstarter.ignite

Changelog
---------

.. _release-0.8.1:

0.8.1
    * Don't need to import pkg_resources when venvstarter is imported
    * Don't need pip as a dependency anymore

.. _release-0.8:

0.8
    * Fix to the python version checks

      * Version checks no longer fail because of using bytes like a str
      * Changed the check order so pythonx is checked before pythonx.y is checked

.. _release-0.7:

0.7
    * Fix so that this continues to work with newer versions of pip

Pre 0.7
    No changelog was kept

Tests
-----

To run the tests you must first create a ``pythons.json`` in the root of your
checkout of venvstarter that tells the tests where to find each version of
Python:

.. code-block:: python

  {
    "python3.6": "~/.pyenv/versions/3.6.13/bin/python",
    "python3.7": "~/.pyenv/versions/3.7.10/bin/python",
    "python3.8": "~/.pyenv/versions/3.8.10/bin/python",
    "python3.9": "~/.pyenv/versions/3.9.5/bin/python"
  }

In this example I'm using pyenv to get copies of each Python. Using pyenv isn't
a requirement, but it does make it easy! There is nothing in the tests that rely
on features in any particular version, and so the minor patch of each version is
irrelevant. All that matters is having some version of 3.6, 3.7, 3.8 and 3.9.

I recommend running the tests in a virtualenv. I use virtualenvwrapper for this
but you can also do a ``python3 -m venv my_venv`` somewhere and use that.

Then once you're in a virtualenv::

  > python -m pip install -e ".[tests]"
  > ./test.sh
