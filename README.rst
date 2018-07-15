Venvstarter
===========

Program to bootstrap a virtualenv for your program!

Full documentation at http://venvstarter.readthedocs.io

Installation
------------

Just use pip!::

    $ pip install venvstarter

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

0.8
    * Fix to the python version checks

      * Version checks no longer fail because of using bytes like a str
      * Changed the check order so pythonx is checked before pythonx.y is checked

0.7
    * Fix so that this continues to work with newer versions of pip

Pre 0.7
    No changelog was kept
