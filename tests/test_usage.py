# coding: spec

import pytest
import time
import json

pytestmark = pytest.mark.usage_tests

describe "Finding the right version":
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
                __import__("venvstarter").manager.add_local_dep(
                    path, version_file=["thing", "__init__.py"], name="thinger=={version}"
                ).run("thing")

            with pytest.helpers.make_script(
                script, json.dumps(creator.path), prepare_venv=True
            ) as filename:
                output = creator.output(filename, "and", "it", "works")
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
                output = creator.output(filename, "and", "it", "works")
                diff1 = time.time() - start
                split = output.split("\n")
                assert len(split) > 1
                assert split[-1] == "dict2xml <class 'module'>"

                start = time.time()
                output = creator.output(filename, "and", "it", "works")
                diff2 = time.time() - start
                split = output.split("\n")
                assert len(split) == 1
                assert output == "dict2xml <class 'module'>"

                assert diff1 - diff2 > 0.5
