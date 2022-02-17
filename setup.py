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
        [ 'pytest>=7.0.1'
        , 'noseOfYeti==2.3.1'
        , "pytest-parallel==0.1.1"
        , 'rainbow_logging_handler==2.2.2'
        , "pytest-helpers-namespace==2021.12.29"
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
