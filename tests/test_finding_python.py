import pytest

from venvstarter import PythonHandler


class TestPythonHandler:
    class TestFindingTheRightPython:
        def test_defaults_max_version_to_whatever_python3_python_and_sys_executable_are(
            self,
        ) -> None:
            with pytest.helpers.PATH.configure(
                "3.10", "3.11", "3.12", python3="3.11", python="3.11", mock_sys="3.11"
            ):
                PythonHandler("3.10", None).find() == pytest.helpers.pythons["3.11"]

            with pytest.helpers.PATH.configure(
                "3.10", "3.11", "3.12", python3="3.11", python="3.10", mock_sys="3.10"
            ):
                PythonHandler("3.10", None).find() == pytest.helpers.pythons["3.11"]

            with pytest.helpers.PATH.configure(
                "3.10", "3.11", "3.12", python3="3.10", python="3.11", mock_sys="3.10"
            ):
                PythonHandler("3.10", None).find() == pytest.helpers.pythons["3.11"]

            with pytest.helpers.PATH.configure(
                "3.10", "3.11", "3.12", python3="3.10", python="3.10", mock_sys="3.11"
            ):
                PythonHandler("3.7", None).find() == pytest.helpers.pythons["3.11"]

        def test_respects_the_actual_max(self) -> None:
            with pytest.helpers.PATH.configure(
                "3.10", "3.11", "3.12", python3="3.12", python="3.12", mock_sys="3.12"
            ):
                PythonHandler("3.10", "3.11").find() == pytest.helpers.pythons["3.11"]

            with pytest.helpers.PATH.configure(
                "3.10", "3.11", "3.12", python3="3.10", python="3.10", mock_sys="3.10"
            ):
                PythonHandler("3.10", "3.11").find() == pytest.helpers.pythons["3.11"]

            with pytest.helpers.PATH.configure(
                "3.10", "3.11", "3.12", python3="3.12", python="3.10", mock_sys="3.10"
            ):
                PythonHandler("3.10", "3.11").find() == pytest.helpers.pythons["3.11"]

            with pytest.helpers.PATH.configure(
                "3.10", "3.11", "3.12", python3="3.10", python="3.12", mock_sys="3.10"
            ):
                PythonHandler("3.10", "3.11").find() == pytest.helpers.pythons["3.11"]

            with pytest.helpers.PATH.configure(
                "3.10", "3.11", "3.12", python3="3.10", python="3.10", mock_sys="3.12"
            ):
                PythonHandler("3.10", "3.11").find() == pytest.helpers.pythons["3.11"]

        def test_defaults_max_to_the_specified_min_if_the_main_ones_are_less(
            self,
        ) -> None:
            with pytest.helpers.PATH.configure(
                "3.10", "3.12", python3="3.10", python="3.10", mock_sys="3.10"
            ):
                with pytest.raises(
                    Exception,
                    match="Couldn't find a suitable python!\nWanted between 3.11.0 and 3.11.0",
                ):
                    PythonHandler("3.11", None).find()

        def test_steps_through_versions(self) -> None:
            with pytest.helpers.PATH.configure(
                "3.10", "3.12", python3="3.12", python="3.10", mock_sys="3.12"
            ):
                PythonHandler("3.10", "3.12").find() == pytest.helpers.pythons["3.12"]

        def test_works_when_there_is_only_one_version(self) -> None:
            with pytest.helpers.PATH.configure(
                "3.12", python3="3.12", python="3.12", mock_sys="3.12"
            ):
                PythonHandler("3.12", "3.12").find() == pytest.helpers.pythons["3.12"]
