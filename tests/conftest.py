from venvstarter import PythonHandler, FailedToGetOutput
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


class PythonsFinder:
    def __init__(self, made_venvs):
        self.made_venvs = made_venvs

    def pythons_json(self, want):
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

        missing = want - set(pythons)
        if missing:
            pytest.exit(f"Missing entries in pythons.json for {', '.join(missing)}")

        return pythons

    def normalise_python_location(self, pythons, k):
        location = os.path.expanduser(pythons[k])
        if os.name == "nt":
            location = location.replace("/", "\\")

        if not os.path.isfile(location):
            pytest.exit(f"Entry for {k} ({location}) is not a file")

        _, version_info = PythonHandler().version_for(location, raise_error=True)
        assert version_info is not None
        got = "python{0}.{1}".format(*version_info.version)
        if got != k:
            pytest.exit(f"Entry for {k} is for a different version of python ({got})")

        return location

    def make_venv(self, python_exe, version, errors):
        venv_location = os.path.join(self.made_venvs, f"venv{version}")
        if not os.path.exists(venv_location):
            PythonHandler().run_command(
                python_exe,
                f"""
                import json
                import venv
                venv.create({json.dumps(venv_location)}, with_pip=True)
            """,
            )

        if os.name == "nt":
            py = os.path.join(venv_location, "Scripts", "python.exe")
        else:
            py = os.path.join(venv_location, "bin", "python")

        if not os.path.exists(py):
            if errors:
                if os.path.exists(venv_location):
                    assert False, ("venv doesn't exist", venv_location)
                else:
                    assert False, ("Couldn't find python", os.listdir(venv_location))

            if os.path.exists(venv_location):
                shutil.rmtree(venv_location)

            return

        return venv_location, py

    def ensure_venvstarter(self, python_exe):
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                PythonHandler().run_command(python_exe, "import venvstarter", cwd=tmpdir)
        except FailedToGetOutput:
            subprocess.run(
                [python_exe, "-m", "pip", "install", os.path.join(this_dir, "..")],
                check=True,
            )

    def ensure_venvstarter_version(self, python_exe, venv_location, errors):

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                vsver = PythonHandler().get_output(
                    python_exe, "import venvstarter; print(venvstarter.VERSION)", cwd=tmpdir
                )
        except FailedToGetOutput as error:
            if errors:
                pytest.exit(f"Failed to ensure venvstarter version is correct: {error}")

            shutil.rmtree(venv_location)
            return False
        else:
            want = __import__("venvstarter").VERSION
            if vsver != want:
                if errors:
                    assert vsver == want
                else:
                    shutil.rmtree(venv_location)
                    return False

    def find(self):
        want = set(["python3.6", "python3.7", "python3.8", "python3.9"])
        pythons = self.pythons_json(want)
        for k in want:
            location = self.normalise_python_location(pythons, k)

            py = None
            for errors in (False, True):
                result = self.make_venv(location, k, errors)
                if not result:
                    continue

                venv_location, py = result
                self.ensure_venvstarter(py)
                if not self.ensure_venvstarter_version(py, venv_location, errors):
                    continue

            assert py is not None and os.path.exists(py)
            pythons[k] = py

        return Pythons(pythons)


class PATH:
    def __init__(self, pythons):
        self.pythons = pythons

    @contextmanager
    def configure(self, *versions, python3=None, python=False):
        tmpdir = None

        class Empty:
            pass

        before = os.environ.get("PATH", Empty)
        try:
            tmpdir = tempfile.mkdtemp(
                suffix=f'__INCLUDING__-{"_".join(str(v) for v in versions)}-python={python}-python3={python3}'
            )

            def link(executable, *, end):
                os.link(executable, os.path.join(tmpdir, f"python{end}"))

            for version in versions:
                link(self.pythons[version], end=str(version))
                if version == python3:
                    link(self.pythons[version], end="3")
                if version == python:
                    link(self.pythons[version], end="")

            if python3 is None:
                link(sys.executable, end="3")
            if python is None:
                link(sys.executable, end="")

            os.environ["PATH"] = tmpdir
            yield
        finally:
            if tmpdir is not None and os.path.exists(tmpdir):
                shutil.rmtree(tmpdir)
            if before is Empty:
                if "PATH" in os.environ:
                    del os.environ["PATH"]
            else:
                os.environ["PATH"] = before


def assertPythonVersion(python_exe, version):
    want = StrictVersion(version)
    _, got = PythonHandler().version_for(python_exe, raise_error=True)
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
                cmd = [exe or sys.executable, location]
            subprocess.run(
                cmd,
                env={**os.environ, "VENVSTARTER_ONLY_MAKE_VENV": "1"},
                check=True,
            )

        yield location
    finally:
        if directory and os.path.exists(directory):
            shutil.rmtree(directory)


class DirectoryCreator:
    def __init__(self):
        self.files = {}

    def add(self, *path, content):
        self.files[path] = content
        if hasattr(self, "path"):
            self.write(path, content)

    def write(self, path, content):
        location = os.path.join(self.path, *path)
        parent = os.path.dirname(location)
        if not os.path.exists(parent):
            os.makedirs(parent)
        with open(location, "w") as fle:
            fle.write(dedent(content))

    def __enter__(self):
        if not hasattr(self, "path"):
            self.path = tempfile.mkdtemp()
        for path, content in self.files.items():
            self.write(path, content)
        return self

    def __exit__(self, exc_typ, exc, tb):
        if hasattr(self, "path") and os.path.exists(self.path):
            shutil.rmtree(self.path)
            del self.path

    def output(self, venvstarter_script_filename, *args):
        assert hasattr(self, "path")
        try:
            output = (
                subprocess.check_output(
                    list(PythonHandler().with_shebang(venvstarter_script_filename, *args)),
                    stderr=subprocess.PIPE,
                )
                .strip()
                .decode()
            )
        except subprocess.CalledProcessError as error:
            stde = ""
            if error.stderr:
                stde = error.stderr.decode()
            assert False, f"Failed to run command ({venvstarter_script_filename}, {args}): {stde}"
        return output


made_venvs = None


def pytest_configure(config):
    config.addinivalue_line("markers", "focus: mark test to run")
    config.addinivalue_line(
        "markers",
        "creation_tests: mark tests that are slow because they go over different versions of python",
    )
    config.addinivalue_line(
        "markers", "usage_tests: mark tests that are slow because they install things"
    )

    if not hasattr(pytest, "helpers"):
        return

    mv = None
    if "TEST_VENVS" in os.environ:
        mv = os.environ["TEST_VENVS"]
        if not os.path.exists(mv):
            os.makedirs(mv)
    else:
        global made_venvs
        made_venvs = tempfile.mkdtemp()
        mv = made_venvs

    pythons = PythonsFinder(mv).find()
    pytest.helpers.register(make_script)
    pytest.helpers.register(DirectoryCreator, name="directory_creator")
    pytest.helpers.register(assertPythonVersion)

    pytest.helpers._registry["PATH"] = PATH(pythons)
    pytest.helpers._registry["pythons"] = pythons


def pytest_unconfigure(config):
    if made_venvs and os.path.exists(made_venvs):
        shutil.rmtree(made_venvs)
