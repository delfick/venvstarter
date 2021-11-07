Changelog
---------

.. _release-0.10.0:

0.10.0 - 8 November 2021
  * Add Official python3.10 support.
  * Drop official support for python3.6
  * The default value for min_python is now python3.7
  * Will now recreate the venv if the target python no longer exists

.. _release-0.9.1:

0.9.1 - 14 July 2021
  * Always use shebang

.. _release-0.9.0:

0.9.0 - 12 July 2021
  * Python3 only
  * New manager API
  * New docs
  * First class Windows support
  * No longer rely on distutils, which will be deprecated after 3.10

.. _release-0.8.1:

0.8.1 - 27 November 2018
  * Don't need to import pkg_resources when venvstarter is imported
  * Don't need pip as a dependency anymore

.. _release-0.8:

0.8 - 15 July 2018
  * Fix to the python version checks
  
    * Version checks no longer fail because of using bytes like a str
    * Changed the check order so pythonx is checked before pythonx.y is checked

.. _release-0.7:

0.7 - 15 April 2018
  * Fix so that this continues to work with newer versions of pip

Pre 0.7
  No changelog was kept
