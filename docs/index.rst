Venvstarter
===========

Program to bootstrap a virtualenv for your program!

Full documentation at http://venvstarter.readthedocs.io

Installation
------------

venvstarter is python3 only and I recommend installing using pip::

    $ python3 -m pip install venvstarter

Usage
-----

This project exists to bootstrap an environment for a particular program.
For example running the `harpoon <https://harpoon.readthedocs.io>`_ project.
To run a version of harpoon, a file can be made that calls out to venvstarter
to manage a virtualenv with the correct version of harpoon and then call out
to the ``harpoon`` script that is created.

An example layout would be::

    project/
        docker/
            harpoon
            harpoon.yml
        ...

Where ``project/docker/harpoon`` is executable and contains:

.. code-block:: python

    #!/usr/bin/env python3

    (__import__("venvstarter").manager("harpoon")
        .add_dep("harpoon==0.16.1")
        .min_python(3.7)
        .env(HARPOON_CONFIG=("{venv_parent}", "harpoon.yml"))
        .run()
        )

And running::

    > ./docker/harpoon list

Is equivalent to::

    > python3 -m venv ./docker/.harpoon
    > ./docker/.harpoon/bin/python -m pip install harpoon==0.16.1
    > HARPOON_CONFIG=./docker/harpoon.yml ./docker/.harpoon/bin/harpoon list

If the virtualenv already exists then it doesn't remake it. If the dependencies
are already the correct version then pip is not used to install anything.

.. toctree::
    :hidden:

    changelog
