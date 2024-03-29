# coding: spec

import json
import os
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.usage_tests

describe "Finding the right version":

    it "can be used to read a requirements.txt":
        with pytest.helpers.directory_creator() as creator:

            creator.add(
                "requirements.txt",
                content="""
                dict2xml
                alt-pytest-asyncio==0.7.2
                """,
            )
            creator.add(
                "start",
                content="""
                #!/usr/bin/env python
                __import__("venvstarter").manager("python").add_requirements_file("{here}", "requirements.txt").run()
                """,
                mode=0o700,
            )

            output = pytest.helpers.get_output(
                str(creator.path / "start"),
                "-c",
                "import dict2xml; import alt_pytest_asyncio; print('yay')",
            ).split("\n")
            assert output[-1] == "yay"

    it "can be used to symlink install and run a local package":
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

            def script(path):
                __import__("venvstarter").manager("thing").add_local_dep(
                    path, version_file=["thing", "__init__.py"], name="thinger=={version}"
                ).run()

            with pytest.helpers.make_script(
                script, repr(str(creator.path)), prepare_venv=True
            ) as filename:
                output = pytest.helpers.get_output(filename, "and", "it", "works")
                assert output == "THINGY and it works"

                creator.add(
                    "pyproject.toml",
                    content="""
                    [build-system]
                    requires = ["hatchling"]
                    build-backend = "hatchling.build"

                    [project]
                    name = "thinger"
                    dynamic = ["version"]
                    dependencies = [
                        "dict2xml==1.7.0",
                    ]

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
                creator.add("thing", "__init__.py", content="VERSION = '0.2'")
                creator.add(
                    "thing",
                    "main.py",
                    content="""
                    import dict2xml
                    import sys

                    def main():
                        print("dict2xml", type(dict2xml))
                    """,
                )

                start = time.time()
                output = pytest.helpers.get_output(filename, "and", "it", "works")
                diff1 = time.time() - start
                split = output.split("\n")
                assert len(split) > 1
                assert split[-1] == "dict2xml <class 'module'>"

                start = time.time()
                output = pytest.helpers.get_output(filename, "and", "it", "works")
                diff2 = time.time() - start
                split = output.split("\n")
                assert len(split) == 1
                assert output == "dict2xml <class 'module'>"

                assert diff1 - diff2 > 0.5

    it "can be used to add a pypi dep":

        def script():
            __import__("venvstarter").manager("python").add_pypi_deps(
                "dict2xml", "alt-pytest-asyncio==0.7.2"
            ).run()

        with pytest.helpers.make_script(script, prepare_venv=True) as filename:
            output = pytest.helpers.get_output(
                filename,
                "-c",
                "import dict2xml; import alt_pytest_asyncio; print('yay')",
            ).split("\n")
            assert output[-1] == "yay"

    it "can be used to make sure a dependency isn't binary":

        def script():
            __import__("venvstarter").manager("python").add_pypi_deps("noseOfYeti[black]").run()

        with pytest.helpers.make_script(script, prepare_venv=True) as filename:
            output = pytest.helpers.get_output(
                filename, "-c", "import black; print(black.__file__)"
            ).split("\n")
            if not output[-1].endswith(".so"):
                pytest.skip("black doesn't install as binary on this system")

            def script():
                __import__("venvstarter").manager("python").add_pypi_deps(
                    "noseOfYeti[black]"
                ).add_no_binary("black").run()

            pytest.helpers.write_script(script, prepare_venv=True, filename=filename)

            output = pytest.helpers.get_output(
                filename, "-c", "import black; print(black.__file__)"
            ).split("\n")
            assert not output[-1].endswith(".so")

    it "can be used to add environment variables":

        def script():
            __import__("venvstarter").manager("python").add_env(
                ONE="1",
                TWO="{home}",
                THREE=("{home}", "one"),
                FOUR="{here}",
                FIVE=("{venv_parent}", "things"),
            ).run()

        with pytest.helpers.make_script(script, prepare_venv=True) as filename:
            os.environ["SIX"] = "20"
            try:
                output = pytest.helpers.get_output(
                    filename,
                    "-c",
                    "import json; import os; print(json.dumps(dict(os.environ)))",
                ).split("\n")[-1]
            finally:
                del os.environ["SIX"]

            wanted = dict(os.environ)
            wanted.update(
                {
                    "ONE": "1",
                    "TWO": str(Path.home()),
                    "THREE": str(Path.home() / "one"),
                    "FOUR": str(filename.parent),
                    "FIVE": str(filename.parent / "things"),
                    "SIX": "20",
                }
            )
            assert json.loads(output) == wanted
