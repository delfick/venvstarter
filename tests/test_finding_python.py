# coding: spec

import pytest

from venvstarter import PythonHandler

describe "PythonHandler":
    describe "finding the right python":
        it "defaults max version to whatever python3, python and sys.executable are":
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

        it "respects the actual max":
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

        it "defaults max to the specified min if the main ones are less":
            with pytest.helpers.PATH.configure(
                3.7, 3.9, "3.10", python3=3.7, python=3.7, mock_sys=3.7
            ):
                with pytest.raises(
                    Exception,
                    match="Couldn't find a suitable python!\nWanted between 3.8.0 and 3.8.0",
                ):
                    PythonHandler("3.8", None).find()

        it "steps through versions":
            with pytest.helpers.PATH.configure(
                3.7, 3.9, "3.10", python3="3.10", python=3.7, mock_sys="3.10"
            ):
                PythonHandler("3.8", "3.9").find() == pytest.helpers.pythons[3.9]

        it "works when there is only one version":
            with pytest.helpers.PATH.configure(3.8, python3=3.8, python=3.8, mock_sys=3.8):
                PythonHandler(3.8, 3.8).find() == pytest.helpers.pythons[3.8]
