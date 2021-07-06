# coding: spec

from venvstarter import PythonHandler
import pytest


describe "PythonHandler":
    describe "finding the right python":
        it "defaults max version to whatever python3, python and sys.executable are":
            with pytest.helpers.PATH.configure(
                3.6, 3.8, 3.9, python3=3.8, python=3.8, mock_sys=3.8
            ):
                PythonHandler("3.6", None).find() == pytest.helpers.pythons[3.8]

            with pytest.helpers.PATH.configure(
                3.6, 3.8, 3.9, python3=3.9, python=3.8, mock_sys=3.8
            ):
                PythonHandler("3.6", None).find() == pytest.helpers.pythons[3.9]

            with pytest.helpers.PATH.configure(
                3.6, 3.8, 3.9, python3=3.8, python=3.9, mock_sys=3.8
            ):
                PythonHandler("3.6", None).find() == pytest.helpers.pythons[3.9]

            with pytest.helpers.PATH.configure(
                3.6, 3.8, 3.9, python3=3.8, python=3.8, mock_sys=3.9
            ):
                PythonHandler("3.6", None).find() == pytest.helpers.pythons[3.9]

        it "respects the actual max":
            with pytest.helpers.PATH.configure(
                3.6, 3.8, 3.9, python3=3.8, python=3.8, mock_sys=3.8
            ):
                PythonHandler("3.6", "3.7").find() == pytest.helpers.pythons[3.7]

            with pytest.helpers.PATH.configure(
                3.6, 3.8, 3.9, python3=3.9, python=3.8, mock_sys=3.8
            ):
                PythonHandler("3.6", "3.7").find() == pytest.helpers.pythons[3.7]

            with pytest.helpers.PATH.configure(
                3.6, 3.8, 3.9, python3=3.8, python=3.9, mock_sys=3.8
            ):
                PythonHandler("3.6", "3.7").find() == pytest.helpers.pythons[3.7]

            with pytest.helpers.PATH.configure(
                3.6, 3.8, 3.9, python3=3.8, python=3.8, mock_sys=3.9
            ):
                PythonHandler("3.6", "3.7").find() == pytest.helpers.pythons[3.7]

        it "defaults max to the specified min if the main ones are less":
            with pytest.helpers.PATH.configure(
                3.6, 3.8, 3.9, python3=3.6, python=3.6, mock_sys=3.6
            ):
                with pytest.raises(
                    Exception,
                    match="Couldn't find a suitable python!\nWanted between 3.7.0 and 3.7.0",
                ):
                    PythonHandler("3.7", None).find()

        it "steps through versions":
            with pytest.helpers.PATH.configure(
                3.6, 3.8, 3.9, python3=3.9, python=3.6, mock_sys=3.9
            ):
                PythonHandler("3.7", "3.8").find() == pytest.helpers.pythons[3.8]

        it "works when there is only one version":
            with pytest.helpers.PATH.configure(3.7, python3=3.7, python=3.7, mock_sys=3.7):
                PythonHandler(3.7, 3.7).find() == pytest.helpers.pythons[3.7]
