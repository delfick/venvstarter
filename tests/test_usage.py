# coding: spec

import pytest
import time
import json
import os

pytestmark = pytest.mark.usage_tests

describe "Finding the right version":

    it "can be used to read a requirements.txt":
        with pytest.helpers.directory_creator() as creator:

            creator.add(
                "requirements.txt",
                content="""
                dict2xml
                pip-chill
                """,
            )
            creator.add(
                "start",
                content="""
                #!/usr/bin/env python
                __import__("venvstarter").manager(None).add_requirements_file("{here}", "requirements.txt").run()
                """,
                mode=0o700,
            )

            output = pytest.helpers.get_output(
                os.path.join(creator.path, "start"),
                "-c",
                "import dict2xml; import pip_chill; print('yay')",
            ).split("\n")
            assert output[-1] == "yay"

    it "can be used to symlink install and run a local package":
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

            def script(path):
                __import__("venvstarter").manager("thing").add_local_dep(
                    path, version_file=["thing", "__init__.py"], name="thinger=={version}"
                ).run()

            with pytest.helpers.make_script(
                script, json.dumps(creator.path), prepare_venv=True
            ) as filename:
                output = pytest.helpers.get_output(filename, "and", "it", "works")
                assert output == "THINGY and it works"

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

                        , install_requires =
                          [ 'dict2xml==1.7.0'
                          ] 
                        )
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
            __import__("venvstarter").manager(None).add_pypi_deps("dict2xml", "pip-chill").run()

        with pytest.helpers.make_script(script, prepare_venv=True) as filename:
            output = pytest.helpers.get_output(
                filename,
                "-c",
                "import dict2xml; import pip_chill; print('yay')",
            ).split("\n")
            assert output[-1] == "yay"

    it "can be used to add environment variables":

        def script():
            __import__("venvstarter").manager(None).add_env(
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
                    "TWO": os.path.expanduser("~"),
                    "THREE": os.path.join(os.path.expanduser("~"), "one"),
                    "FOUR": os.path.dirname(filename),
                    "FIVE": os.path.join(os.path.dirname(filename), "things"),
                    "SIX": "20",
                }
            )
            assert json.loads(output) == wanted
