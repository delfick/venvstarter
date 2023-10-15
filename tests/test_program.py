# coding: spec

import os
from contextlib import contextmanager
from pathlib import Path

import pytest


@contextmanager
def entry_point(script):
    with pytest.helpers.directory_creator() as creator:

        creator.add(
            "setup.py",
            content="""
        from setuptools import setup, find_packages
        from thing import VERSION

        setup(
              name = 'thinger'
            , version = VERSION
            , packages = find_packages(include="thing.*")

            , entry_points =
              { 'console_scripts' :
                [ 'thing = thing.main:main'
                ]
              }
            )
        """,
        )
        creator.add("thing", "__init__.py", content="VERSION = '0.1'")
        creator.add(
            "thing",
            "main.py",
            content="""
        import sys

        def main():
            print("THINGY", *sys.argv[1:])
        """,
        )

        def decorator(path):
            def decorated(script):
                script().add_local_dep(
                    path, version_file=["thing", "__init__.py"], name="thinger=={version}"
                ).run()

            return decorated

        with pytest.helpers.make_script(
            script, repr(str(creator.path)), prepare_venv=True, decorator=decorator
        ) as filename:
            yield filename


describe "Different programs":

    @pytest.mark.parametrize("version", [3.7, 3.8, 3.9, "3.10", "3.11"])
    it "can be None", version:

        def script():
            return __import__("venvstarter").manager(None)

        with entry_point(script) as filename:
            output = pytest.helpers.get_output(filename).split("\n")
            output = pytest.helpers.get_output(filename)
            assert output == ""

            output = pytest.helpers.get_output(filename, "thing", "one", "two")
            assert output == "THINGY one two"

    @pytest.mark.parametrize("version", [3.7, 3.8, 3.9, "3.10", "3.11"])
    it "can be an entry point", version:

        def script():
            return __import__("venvstarter").manager("thing")

        with entry_point(script) as filename:
            output = pytest.helpers.get_output(filename, "one", "two").split("\n")
            assert output[-1] == "THINGY one two"

    @pytest.mark.parametrize("version", [3.7, 3.8, 3.9, "3.10", "3.11"])
    it "can be a binary", version:

        def script():
            return __import__("venvstarter").manager("python")

        with entry_point(script) as filename:
            output = pytest.helpers.get_output(filename, "-c", "print('I am a python')").split("\n")
            assert output[-1] == "I am a python"

    @pytest.mark.parametrize("version", [3.7, 3.8, 3.9, "3.10", "3.11"])
    it "can be a list", version:

        def script():
            return __import__("venvstarter").manager(["python", "-c"])

        with entry_point(script) as filename:
            output = pytest.helpers.get_output(filename, "print('I am a snake')").split("\n")
            assert output[-1] == "I am a snake"

        def script():
            return __import__("venvstarter").manager(["thing", "parsel"])

        with entry_point(script) as filename:
            output = pytest.helpers.get_output(filename, "tongue").split("\n")
            assert output[-1] == "THINGY parsel tongue"

        if os.name != "nt":

            def script():
                return __import__("venvstarter").manager(
                    [__import__("shutil").which("cat"), __file__]
                )
                print("this should be last!")

            with entry_point(script) as filename:
                output = pytest.helpers.get_output(filename).split("\n")
                assert output[-1] == '    print("this should be last!")'

    @pytest.mark.parametrize("version", [3.7, 3.8, 3.9, "3.10", "3.11"])
    it "can be a function that doesn't do anything", version:

        def script():
            def runme(venv_location, args):
                print(venv_location)

            return __import__("venvstarter").manager(runme)

        with entry_point(script) as filename:
            output = pytest.helpers.get_output(filename, "tongue").split("\n")
            assert output[-1] == str(Path(filename).parent / ".venv")

    @pytest.mark.parametrize("version", [3.7, 3.8, 3.9, "3.10", "3.11"])
    it "can be a function that returns a path to run", version:

        def script():
            def runme(venv_location, args):
                return "python"

            return __import__("venvstarter").manager(runme)

        with entry_point(script) as filename:
            output = pytest.helpers.get_output(filename, "-c", 'print("bye")').split("\n")
            assert output[-1] == "bye"

        def script():
            def runme(venv_location, args):
                res = ["thing", "what", *args]
                args.clear()
                return res

            return __import__("venvstarter").manager(runme)

        with entry_point(script) as filename:
            output = pytest.helpers.get_output(filename, "is", "it").split("\n")
            assert output[-1] == "THINGY what is it"
