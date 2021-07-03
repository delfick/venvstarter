from distutils.version import StrictVersion
from contextlib import contextmanager
from textwrap import dedent
import subprocess
import tempfile
import inspect
import shutil
import pytest
import json
import sys
import os

this_dir = os.path.dirname(__file__)


class Pythons:
    def __init__(self, locations):
        self.locations = locations

    def __iter__(self):
        for key in sorted(self.locations):
            yield float(key[len("python") :])

    def __getitem__(self, key):
        if not isinstance(key, float):
            assert (
                False
            ), f"Can only get a python location using a float of 3.6, 3.7, etc. Used {key}"

        if int(key) == key:
            assert (
                False
            ), f"Can only get a python location using a float of 3.6, 3.7, etc. Used {key}"

        return self.locations[f"python{key:.1f}"]


def find_pythons(made_venvs):
    location = os.path.join(this_dir, "..", "pythons.json")
    if not os.path.isfile(location):
        pytest.exit(
            "You must have a pythons.json in the root of your venvstarter that says where each python can be found"
        )
    with open(location) as fle:
        pythons = json.load(fle)

    if not isinstance(pythons, dict):
        pytest.exit(
            'The pythons.json must be a dictionary of {"python3.6": <location>, "python3.7": <location>, ...}'
        )

    want = set(["python3.6", "python3.7", "python3.8", "python3.9"])
    missing = want - set(pythons)
    if missing:
        pytest.exit(f"Missing entries in pythons.json for {', '.join(missing)}")

    for k in want:
        location = os.path.expanduser(pythons[k])
        if os.name == "nt":
            location = location.replace("/", "\\")

        if not os.path.isfile(location):
            pytest.exit(f"Entry for {k} ({location}) is not a file")

        question = [location, "-c", "import sys, json; print(json.dumps(list(sys.version_info)))"]

        try:
            version_info = (
                subprocess.check_output(question, stderr=subprocess.PIPE).strip().decode()
            )
        except subprocess.CalledProcessError as error:
            stde = error.stderr.decode()
            pytest.exit(f"Failed to call out to entry for {k}: {error}:\n{stde}")
        else:
            got = "python{0}.{1}".format(*json.loads(version_info))
            if got != k:
                pytest.exit(f"Entry for {k} is for a different version of python ({got})")

        py = None
        for i in range(2):
            venv_location = os.path.join(made_venvs, f"venv{k}")
            if not os.path.exists(venv_location):
                subprocess.run([location, "-m", "venv", f"venv{k}"], cwd=made_venvs, check=True)

            if os.name == "nt":
                py = os.path.join(venv_location, "Scripts", "python")
            else:
                py = os.path.join(venv_location, "bin", "python")

            if not os.path.exists(py):
                shutil.rmtree(venv_location)
                continue

            question = [location, "-c", "import venvstarter"]
            try:
                subprocess.check_output(question, stderr=subprocess.PIPE).strip().decode()
            except subprocess.CalledProcessError:
                subprocess.run([py, "-m", "pip", "install", "-e", os.path.join(this_dir, "..")])

            question = [location, "-c", "from venvstarter import VERSION; print(VERSION)"]

            try:
                vsver = subprocess.check_output(question, stderr=subprocess.PIPE).strip().decode()
            except subprocess.CalledProcessError as error:
                stde = error.stderr.decode()
                if i == 0:
                    shutil.rmtree(venv_location)
                    continue
                else:
                    pytest.exit("Failed to ensure venvstarter version is correct")
            else:
                want = __import__("venvstarter").VERSION
                if i == 0 and vsver != want:
                    shutil.rmtree(venv_location)
                    continue
                else:
                    assert vsver == want

        assert py is not None and os.path.exists(py)
        pythons[k] = py

    return Pythons(pythons)


class PATH:
    def __init__(self, pythons):
        self.pythons = pythons

    @contextmanager
    def configure(self, *versions):
        PATH = []
        for version in versions:
            PATH.append(os.path.dirname(self.pythons[version]))

        class Empty:
            pass

        before = os.environ.get("PATH", Empty)
        try:
            os.environ["PATH"] = ":".join(PATH)
            yield
        finally:
            if before is Empty:
                if "PATH" in os.environ:
                    del os.environ["PATH"]
            else:
                os.environ["PATH"] = before


def assertPythonVersion(python_exe, version):
    want = StrictVersion(version)

    _, got = __import__("venvstarter").PythonFinder(3, 3).version_for(python_exe)
    assert got is not None, python_exe

    assert want.version[:2] == got.version[:2], (want, got)


@contextmanager
def make_script(func, args="", exe=None, prepare_venv=False):
    script = dedent(inspect.getsource(func))

    directory = None
    try:
        directory = tempfile.mkdtemp()
        location = os.path.join(directory, "starter")

        with open(location, "w") as fle:
            fle.write(
                "\n".join(
                    [
                        f"#!{exe or sys.executable}",
                        "import sys",
                        script,
                        f"script({args})",
                    ]
                )
            )

        with open(location) as fle:
            print(fle.read())
            print("=" * 20)

        os.chmod(location, 0o755)

        if prepare_venv:
            cmd = location
            if os.name == "nt":
                cmd = [exe, location]
            subprocess.run(
                cmd,
                env={**os.environ, "VENVSTARTER_ONLY_MAKE_VENV": "1"},
                shell=True,
                check=True,
            )

        yield location
    finally:
        if directory and os.path.exists(directory):
            shutil.rmtree(directory)


made_venvs = None


def pytest_configure(config):
    config.addinivalue_line("markers", "focus: mark test to run")

    if not hasattr(pytest, "helpers"):
        return

    mv = None
    if "TEST_VENVS" in os.environ:
        mv = os.environ["TEST_VENVS"]
    else:
        global made_venvs
        made_venvs = tempfile.mkdtemp()
        mv = made_venvs

    pythons = find_pythons(mv)
    pytest.helpers.register(make_script)
    pytest.helpers.register(assertPythonVersion)

    pytest.helpers._registry["PATH"] = PATH(pythons)
    pytest.helpers._registry["pythons"] = pythons


def pytest_unconfigure(config):
    if made_venvs and os.path.exists(made_venvs):
        shutil.rmtree(made_venvs)
