import os
from contextlib import contextmanager
from pathlib import Path

import pytest


@contextmanager
def entry_point(script):
    with pytest.helpers.directory_creator() as creator:
        creator.add(
            "pyproject.toml",
            content="""
            [build-system]
            requires = ["hatchling"]
            build-backend = "hatchling.build"

            [project]
            name = "thinger"
            dynamic = ["version"]

            [project.scripts]
            thing = "thing.main:main"

            [tool.hatch.version]
            path = "thing/__init__.py"

            [tool.hatch.build.targets.sdist]
            include = [
                "/thing",
            ]

            [tool.hatch.build.targets.wheel]
            include = [
                "/thing",
            ]
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
                    path,
                    version_file=["thing", "__init__.py"],
                    name="thinger=={version}",
                ).run()

            return decorated

        with pytest.helpers.make_script(
            script, repr(str(creator.path)), prepare_venv=True, decorator=decorator
        ) as filename:
            yield filename


class TestDifferentPrograms:
    @pytest.mark.parametrize("version", ["3.10", "3.11", "3.12"])
    def test_can_be_None(self, version: str) -> None:
        def script():
            return __import__("venvstarter").manager(None)

        with entry_point(script) as filename:
            output = pytest.helpers.get_output(filename).split("\n")
            output = pytest.helpers.get_output(filename)
            assert output == ""

            output = pytest.helpers.get_output(filename, "thing", "one", "two")
            assert output == "THINGY one two"

    @pytest.mark.parametrize("version", ["3.10", "3.11", "3.12"])
    def test_can_be_an_entry_point(self, version: str) -> None:
        def script():
            return __import__("venvstarter").manager("thing")

        with entry_point(script) as filename:
            output = pytest.helpers.get_output(filename, "one", "two").split("\n")
            assert output[-1] == "THINGY one two"

    @pytest.mark.parametrize("version", ["3.10", "3.11", "3.12"])
    def test_can_be_a_binary(self, version: str) -> None:
        def script():
            return __import__("venvstarter").manager("python")

        with entry_point(script) as filename:
            output = pytest.helpers.get_output(
                filename, "-c", "print('I am a python')"
            ).split("\n")
            assert output[-1] == "I am a python"

    @pytest.mark.parametrize("version", ["3.10", "3.11", "3.12"])
    def test_can_be_a_list(self, version: str) -> None:
        def script():
            return __import__("venvstarter").manager(["python", "-c"])

        with entry_point(script) as filename:
            output = pytest.helpers.get_output(filename, "print('I am a snake')").split(
                "\n"
            )
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

    @pytest.mark.parametrize("version", ["3.10", "3.11", "3.12"])
    def test_can_be_a_function_that_does_not_do_anything(self, version: str) -> None:
        def script():
            def runme(venv_location, args):
                print(venv_location)

            return __import__("venvstarter").manager(runme)

        with entry_point(script) as filename:
            output = pytest.helpers.get_output(filename, "tongue").split("\n")
            assert output[-1] == str(Path(filename).parent / ".venv")

    @pytest.mark.parametrize("version", ["3.10", "3.11", "3.12"])
    def test_can_be_a_function_that_returns_a_path_to_run(self, version: str) -> None:
        def script():
            def runme(venv_location, args):
                return "python"

            return __import__("venvstarter").manager(runme)

        with entry_point(script) as filename:
            output = pytest.helpers.get_output(filename, "-c", 'print("bye")').split(
                "\n"
            )
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
