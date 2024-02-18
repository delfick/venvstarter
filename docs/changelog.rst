Changelog
---------

.. _release-0.12.2:

0.12.2 - TBD
    * Improved the bootstrap script and example equivalent
    * Install greater than or equal to pip 24 now

.. _release-0.12.1:

0.12.1 - 26 November 2023
    * Understand ``backports`` packages better

.. _release-0.12.0:

0.12.0 - 7 November 2023
   * Removed support for python3.6
   * Changed packaging to use hatch
   * Pip is made to be greater than 23 when a ``venv`` is used
     unless ``VENVSTARTER_UPGRADE_PIP=0``
   * Removed ``venvstarter.ignite``
   * Added support for python 3.12

.. _release-0.11.0:

0.11.0 - 17 February 2022
   * Ability to say some packages should not be installed as binary

.. _release-0.10.0:

0.10.0 - 8 November 2021
  * Add Official python3.10 support.
  * Drop official support for python3.6
  * The default value for min_python is now python3.7
  * Will now recreate the ``venv`` if the target python no longer exists

.. _release-0.9.1:

0.9.1 - 14 July 2021
  * Always use shebang

.. _release-0.9.0:

0.9.0 - 12 July 2021
  * Python3 only
  * New manager API
  * New docs
  * First class Windows support
  * No longer rely on ``distutils``, which will be deprecated after 3.10

.. _release-0.8.1:

0.8.1 - 27 November 2018
  * Don't need to import pkg_resources when ``venvstarter`` is imported
  * Don't need pip as a dependency anymore

.. _release-0.8:

0.8 - 15 July 2018
  * Fix to the python version checks
  
    * Version checks no longer fail because of using bytes like a ``str``
    * Changed the check order so pythonx is checked before ``pythonx.y`` is checked

.. _release-0.7:

0.7 - 15 April 2018
  * Fix so that this continues to work with newer versions of pip

Pre 0.7
  No changelog was kept
