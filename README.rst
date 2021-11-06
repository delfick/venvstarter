Venvstarter
===========

Program to bootstrap a virtualenv for your program!

Full documentation at http://venvstarter.readthedocs.io

Tests
-----

To run the tests you must first create a ``pythons.json`` in the root of your
checkout of venvstarter that tells the tests where to find each version of
Python:

.. code-block:: python

  {
    "python3.6": "~/.pyenv/versions/3.6.13/bin/python",
    "python3.7": "~/.pyenv/versions/3.7.12/bin/python",
    "python3.8": "~/.pyenv/versions/3.8.12/bin/python",
    "python3.9": "~/.pyenv/versions/3.9.6/bin/python"
    "python3.10": "~/.pyenv/versions/3.10.0/bin/python"
  }

In this example I'm using pyenv to get copies of each Python. Using pyenv isn't
a requirement, but it does make it easy! There is nothing in the tests that rely
on features in any particular version, and so the minor patch of each version is
irrelevant. All that matters is having some version of 3.6, 3.7, 3.8, 3.9 and 3.10.

I recommend running the tests in a virtualenv. I use virtualenvwrapper for this
but you can also do a ``python3 -m venv my_venv`` somewhere and use that.

Then once you're in a virtualenv::

  > python -m pip install -e ".[tests]"
  > ./test.sh
