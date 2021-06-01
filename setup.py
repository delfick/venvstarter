from setuptools import setup

# fmt: off

setup(
      name = "venvstarter"
    , version = "0.8.1"
    , py_modules = ['venvstarter']
    , python_requires = ">= 3.6"

    , author = 'Stephen Moore'
    , license = 'MIT'
    , author_email = 'github@delfick.com'

    , url = "https://github.com/delfick/venvstarter"
    , description = 'Tool to create virtualenvs, manage versions of packages in it and use it start a particular program'
    , long_description = open("README.rst").read()
    )

# fmt: on
