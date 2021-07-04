# coding: spec

import pytest

pytestmark = pytest.mark.creation_tests

describe "Finding the right version":

    @pytest.mark.parametrize("version", [3.6, 3.7, 3.8, 3.9])
    it "will always use current version if no max is specified", version:

        def script():
            __import__("venvstarter").manager.run("python")

        with pytest.helpers.PATH.configure(version, python=3.9, python3=3.9):
            exe = pytest.helpers.pythons[version]
            with pytest.helpers.make_script(script, exe=exe, prepare_venv=True) as filename:
                pytest.helpers.assertPythonVersion(filename, str(version))

    @pytest.mark.parametrize("version", [3.6, 3.7, 3.8, 3.9])
    it "will use the only version available if within min and max", version:

        def script(version):
            __import__("venvstarter").manager.min_python(version).run("python")

        for use in pytest.helpers.pythons:
            if use >= version:
                with pytest.helpers.PATH.configure(use, python3=use, python=use):
                    exe = pytest.helpers.pythons[use]
                    with pytest.helpers.make_script(
                        script, str(version), exe=exe, prepare_venv=True
                    ) as filename:
                        pytest.helpers.assertPythonVersion(filename, str(use))
