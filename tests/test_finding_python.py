import pytest

from venvstarter import PythonHandler


class TestPythonHandler:
    class TestFindingTheRightPython:
        def test_defaults_max_version_to_whatever_python3_python_and_sys_executable_are(
            self,
        ) -> None:
            with pytest.helpers.PATH.configure(
                3.7, 3.9, "3.10", python3=3.9, python=3.9, mock_sys=3.9
            ):
                PythonHandler("3.7", None).find() == pytest.helpers.pythons[3.9]

            with pytest.helpers.PATH.configure(
                3.7, 3.9, "3.10", python3=3.10, python=3.9, mock_sys=3.9
            ):
                PythonHandler("3.7", None).find() == pytest.helpers.pythons["3.10"]

            with pytest.helpers.PATH.configure(
                3.7, 3.9, "3.10", python3=3.9, python="3.10", mock_sys=3.9
            ):
                PythonHandler("3.7", None).find() == pytest.helpers.pythons["3.10"]

            with pytest.helpers.PATH.configure(
                3.7, 3.9, "3.10", python3=3.9, python=3.9, mock_sys="3.10"
            ):
                PythonHandler("3.7", None).find() == pytest.helpers.pythons["3.10"]

        def test_respects_the_actual_max(self) -> None:
            with pytest.helpers.PATH.configure(
                3.7, 3.9, "3.10", python3=3.9, python=3.9, mock_sys=3.9
            ):
                PythonHandler("3.7", "3.8").find() == pytest.helpers.pythons[3.8]

            with pytest.helpers.PATH.configure(
                3.7, 3.9, "3.10", python3="3.10", python=3.9, mock_sys=3.9
            ):
                PythonHandler("3.7", "3.8").find() == pytest.helpers.pythons[3.8]

            with pytest.helpers.PATH.configure(
                3.7, 3.9, "3.10", python3=3.9, python="3.10", mock_sys=3.9
            ):
                PythonHandler("3.7", "3.8").find() == pytest.helpers.pythons[3.8]

            with pytest.helpers.PATH.configure(
                3.7, 3.9, "3.10", python3=3.9, python=3.9, mock_sys="3.10"
            ):
                PythonHandler("3.7", "3.8").find() == pytest.helpers.pythons[3.8]

        def test_defaults_max_to_the_specified_min_if_the_main_ones_are_less(
            self,
        ) -> None:
            with pytest.helpers.PATH.configure(
                3.7, 3.9, "3.10", python3=3.7, python=3.7, mock_sys=3.7
            ):
                with pytest.raises(
                    Exception,
                    match="Couldn't find a suitable python!\nWanted between 3.8.0 and 3.8.0",
                ):
                    PythonHandler("3.8", None).find()

        def test_steps_through_versions(self) -> None:
            with pytest.helpers.PATH.configure(
                3.7, 3.9, "3.10", python3="3.10", python=3.7, mock_sys="3.10"
            ):
                PythonHandler("3.8", "3.9").find() == pytest.helpers.pythons[3.9]

        def test_works_when_there_is_only_one_version(self) -> None:
            with pytest.helpers.PATH.configure(
                3.8, python3=3.8, python=3.8, mock_sys=3.8
            ):
                PythonHandler(3.8, 3.8).find() == pytest.helpers.pythons[3.8]
