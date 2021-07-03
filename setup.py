from venvstarter import VERSION

from setuptools import setup

# fmt: off

setup(
      name = "venvstarter"
    , version = VERSION
    , py_modules = ['venvstarter']
    , python_requires = ">= 3.6"

    , extras_require =
      { 'tests':
        [ 'pytest'
        , 'noseOfYeti==2.0.2'
        , "pytest-parallel==0.1.0"
        , 'rainbow_logging_handler==2.2.2'
        , "pytest-helpers-namespace==2021.4.29"
        ]
      }

    , author = 'Stephen Moore'
    , license = 'MIT'
    , author_email = 'github@delfick.com'

    , url = "https://github.com/delfick/venvstarter"
    , description = 'Tool to create virtualenvs, manage versions of packages in it and use it start a particular program'
    , long_description = open("README.rst").read()
    )

# fmt: on
