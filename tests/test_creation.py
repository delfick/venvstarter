# coding: spec

import os

import pytest

from venvstarter import Version

pytestmark = pytest.mark.creation_tests

describe "Finding the right version":

    @pytest.mark.parametrize("version", [3.7, 3.8, 3.9, "3.10"])
    it "will always use current version if no max is specified", version:

        def script():
            __import__("venvstarter").manager("python").min_python("3.6").run()

        with pytest.helpers.PATH.configure(version, python="3.10", python3="3.10"):
            exe = pytest.helpers.pythons[version]
            with pytest.helpers.make_script(script, exe=exe, prepare_venv=True) as filename:
                pytest.helpers.assertPythonVersion(filename, str(version))

    @pytest.mark.parametrize("version", [3.7, 3.8, 3.9, "3.10"])
    it "will use the only version available if within min and max", version:

        def script(version):
            __import__("venvstarter").manager("python").min_python(version).run()

        for use in pytest.helpers.pythons:
            if Version(use) >= Version(version):
                with pytest.helpers.PATH.configure(use, python3=use, python=use):
                    exe = pytest.helpers.pythons[use]
                    with pytest.helpers.make_script(
                        script, str(version), exe=exe, prepare_venv=True
                    ) as filename:
                        pytest.helpers.assertPythonVersion(filename, str(use))

    it "can force the virtualenv to get a new version if the current python doesn't exist":

        def script():
            __import__("venvstarter").manager("python").min_python(3.7).run()

        with pytest.helpers.PATH.configure(3.6, 3.7, python3=3.6, python=3.6, mock_sys=3.6):
            with pytest.helpers.make_script(script, prepare_venv=True) as filename:
                pytest.helpers.assertPythonVersion(filename, "3.7")

                with pytest.helpers.PATH.configure(3.7, 3.8, python3=3.8, python=3.8, mock_sys=3.8):
                    pytest.helpers.write_script(script, filename=filename)
                    pytest.helpers.assertPythonVersion(filename, "3.7")

                def break_location(location):
                    assert location.exists()
                    location.unlink()
                    location.symlink_to(filename.parent / "nowhere")
                    assert not location.exists()

                scripts_folder = filename.parent / ".python"
                if os.name == "nt":
                    python = scripts_folder / "Scripts" / "python"
                    if python.exists():
                        break_location(python)
                    if python.with_suffix(".exe").exists():
                        break_location(python.with_suffix(".exe"))
                else:
                    break_location(scripts_folder / "bin" / "python")

                with pytest.helpers.PATH.configure(3.7, 3.8, python3=3.8, python=3.8, mock_sys=3.8):
                    pytest.helpers.write_script(script, filename=filename)
                    pytest.helpers.assertPythonVersion(filename, "3.8")

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
