from setuptools import setup

setup(
      name = "venvstarter"
    , version = "0.2"
    , py_modules = ['venvstarter']

    , install_requires =
      [ "pip"
      , "argparse"
      , "virtualenv"
      ]

    # metadata for upload to PyPI
    , url = "https://github.com/delfick/venvstarter"
    , author = "Stephen Moore"
    , author_email = "delfick755@gmail.com"
    , description = "Tool to create virtualenvs, manage versions of packages in it and use it start a particular program"
    , license = "MIT"
    , keywords = "docker"
    )

