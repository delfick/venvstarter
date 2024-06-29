import os

import pytest

from venvstarter import Version

pytestmark = pytest.mark.creation_tests


class TestFindingTheRightVersion:
    @pytest.mark.parametrize("version", ["3.10", "3.11", "3.12"])
    def test_will_always_use_current_version_if_no_max_is_specified(
        self, version: str
    ) -> None:
        def script():
            __import__("venvstarter").manager("python").min_python("3.10").run()

        with pytest.helpers.PATH.configure(version, python="3.10", python3="3.10"):
            exe = pytest.helpers.pythons[version]
            with pytest.helpers.make_script(
                script, exe=exe, prepare_venv=True
            ) as filename:
                pytest.helpers.assertPythonVersion(filename, str(version))

    @pytest.mark.parametrize("version", ["3.10", "3.11", "3.12"])
    def test_will_use_only_version_available_if_within_min_and_max(
        self, version: str
    ) -> None:
        def script(version):
            __import__("venvstarter").manager("python").min_python(version).run()

        for use in pytest.helpers.pythons:
            if Version(use) >= Version(version):
                with pytest.helpers.PATH.configure(use, python3=use, python=use):
                    exe = pytest.helpers.pythons[use]
                    with pytest.helpers.make_script(
                        script, repr(str(version)), exe=exe, prepare_venv=True
                    ) as filename:
                        pytest.helpers.assertPythonVersion(filename, str(use))

    def test_can_force_the_virtual_env_to_get_a_new_version_if_the_current_python_does_not_exist(
        self,
    ) -> None:
        def script():
            __import__("venvstarter").manager("python").min_python("3.10").run()

        with pytest.helpers.PATH.configure(
            "3.10", "3.11", python3="3.10", python="3.10", mock_sys="3.10"
        ):
            with pytest.helpers.make_script(script, prepare_venv=True) as filename:
                pytest.helpers.assertPythonVersion(filename, "3.10")

                with pytest.helpers.PATH.configure(
                    "3.10", "3.11", python3="3.12", python="3.12", mock_sys="3.12"
                ):
                    pytest.helpers.write_script(script, filename=filename)
                    pytest.helpers.assertPythonVersion(filename, "3.10")

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

                with pytest.helpers.PATH.configure(
                    "3.10", "3.11", python3="3.12", python="3.12", mock_sys="3.12"
                ):
                    pytest.helpers.write_script(script, filename=filename)
                    pytest.helpers.assertPythonVersion(filename, "3.12")

    def test_can_force_the_virtualenv_to_get_a_new_version(self) -> None:
        def script():
            __import__("venvstarter").manager("python").min_python("3.10").run()

        with pytest.helpers.PATH.configure(
            "3.10", "3.11", python3="3.10", python="3.10", mock_sys="3.10"
        ):
            with pytest.helpers.make_script(script, prepare_venv=True) as filename:
                pytest.helpers.assertPythonVersion(filename, "3.10")

                with pytest.helpers.PATH.configure(
                    "3.10",
                    "3.11",
                    "3.12",
                    python3="3.12",
                    python="3.12",
                    mock_sys="3.12",
                ):
                    pytest.helpers.assertPythonVersion(filename, "3.10")

                    def script():
                        __import__("venvstarter").manager("python").min_python(
                            "3.11"
                        ).run()

                    pytest.helpers.write_script(script, filename=filename)
                    pytest.helpers.assertPythonVersion(filename, "3.12")
