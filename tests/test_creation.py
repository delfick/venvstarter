# coding: spec

import pytest

pytestmark = pytest.mark.creation_tests

describe "Finding the right version":

    @pytest.mark.parametrize("version", [3.6, 3.7, 3.8, 3.9])
    it "will always use current version if no max is specified", version:

        def script():
            __import__("venvstarter").manager("python").run()

        with pytest.helpers.PATH.configure(version, python=3.9, python3=3.9):
            exe = pytest.helpers.pythons[version]
            with pytest.helpers.make_script(script, exe=exe, prepare_venv=True) as filename:
                pytest.helpers.assertPythonVersion(filename, str(version))

    @pytest.mark.parametrize("version", [3.6, 3.7, 3.8, 3.9])
    it "will use the only version available if within min and max", version:

        def script(version):
            __import__("venvstarter").manager("python").min_python(version).run()

        for use in pytest.helpers.pythons:
            if use >= version:
                with pytest.helpers.PATH.configure(use, python3=use, python=use):
                    exe = pytest.helpers.pythons[use]
                    with pytest.helpers.make_script(
                        script, str(version), exe=exe, prepare_venv=True
                    ) as filename:
                        pytest.helpers.assertPythonVersion(filename, str(use))

    it "can force the virtualenv to get a new version":

        def script():
            __import__("venvstarter").manager("python").min_python(3.7).run()

        with pytest.helpers.PATH.configure(3.6, 3.7, python3=3.6, python=3.6, mock_sys=3.6):
            with pytest.helpers.make_script(script, prepare_venv=True) as filename:
                pytest.helpers.assertPythonVersion(filename, "3.7")

                with pytest.helpers.PATH.configure(
                    3.6, 3.7, 3.8, python3=3.8, python=3.8, mock_sys=3.8
                ):
                    pytest.helpers.assertPythonVersion(filename, "3.7")

                    def script():
                        __import__("venvstarter").manager("python").min_python(3.8).run()

                    pytest.helpers.write_script(script, filename=filename)
                    pytest.helpers.assertPythonVersion(filename, "3.8")
