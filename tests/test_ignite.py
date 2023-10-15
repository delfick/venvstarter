# coding: spec

from pathlib import Path

import pytest

describe "ignite":

    @pytest.mark.parametrize("version", [3.7, 3.8, 3.9, "3.10", "3.11"])
    it "works", version:

        def script():
            __import__("venvstarter").ignite(
                __file__,
                "python",
                deps=["dict2xml"],
                env={"THING": "stuff"},
                min_python_version="3.7",
                max_python_version="3.9",
                venv_folder_name=".blah",
            ).run()

        with pytest.helpers.PATH.configure(
            3.7, 3.8, 3.9, "3.10", "3.11", python=version, python3=version, mock_sys=version
        ):
            with pytest.helpers.make_script(script) as filename:
                assert not (Path(filename).parent / ".blah").exists()

                output = pytest.helpers.get_output(
                    filename, "-c", 'import os; import dict2xml; print(os.environ["THING"])'
                ).split("\n")
                assert output[-1] == "stuff"

                assert (Path(filename).parent / ".blah").exists()
