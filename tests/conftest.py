from venvstarter import PythonHandler, FailedToGetOutput
from contextlib import contextmanager
from textwrap import dedent
from unittest import mock
from pathlib import Path
import subprocess
import tempfile
import inspect
import shutil
import pytest
import json
import sys
import os
import re

this_dir = Path(__file__).parent

regexes = {"version": re.compile(r"3\.(6|7|8|9|10)")}


class Pythons:
    def __init__(self, locations):
        self.locations = locations

    def __iter__(self):
        for key in sorted(self.locations):
            yield float(key[len("python") :])

    def __getitem__(self, key):
        if not isinstance(key, (float, str)):
            assert (
                False
            ), f"Can only get a python location using a float or string of 3.6, 3.7, etc. Used {key}"

        key = str(key)
        if not regexes["version"].match(key):
            assert (
                False
            ), f"Can only get a python location using a float or string of 3.6, 3.7, etc. Used {key}"

        return self.locations[f"python{key}"]


class PythonsFinder:
    def __init__(self, made_venvs):
        self.made_venvs = made_venvs

    def pythons_json(self, want):
        location = Path(this_dir) / ".." / "pythons.json"
        if not location.is_file():
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

        return {k: Path(v) for k, v in pythons.items()}

    def normalise_python_location(self, pythons, k):
        location = pythons[k].expanduser()

        if not location.is_file():
            pytest.exit(f"Entry for {k} ({location}) is not a file")

        _, version_info = PythonHandler().version_for(location, raise_error=True)
        assert version_info is not None
        got = "python{0}.{1}".format(*version_info.version)
        if got != k:
            pytest.exit(f"Entry for {k} is for a different version of python ({got})")

        return location

    def make_venv(self, python_exe, version, errors):
        venv_location = self.made_venvs / f"venv{version}"
        if not venv_location.exists():
            PythonHandler().run_command(
                python_exe,
                f"""
                import json
                import venv
                venv.create({json.dumps(str(venv_location))}, with_pip=True)
            """,
            )

        if os.name == "nt":
            py = venv_location / "Scripts" / "python.exe"
        else:
            py = venv_location / "bin" / "python"

        if not py.exists():
            if errors:
                if venv_location.exists():
                    assert False, ("venv doesn't exist", venv_location)
                else:
                    assert False, ("Couldn't find python", venv_location.iterdir())

            if venv_location.exists():
                shutil.rmtree(venv_location)

            return

        return venv_location, py

    def ensure_venvstarter(self, python_exe):
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                PythonHandler().run_command(python_exe, "import venvstarter", cwd=tmpdir)
        except FailedToGetOutput:
            subprocess.run(
                [str(python_exe), "-m", "pip", "install", "-e", str(this_dir.parent)],
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
        want = set(["python3.6", "python3.7", "python3.8", "python3.9", "python3.10"])
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

            assert py is not None and py.exists()
            pythons[k] = py

        return Pythons(pythons)


class PATH:
    def __init__(self, pythons):
        self.pythons = pythons

    def link(self, tmpdir, paths, executable, *, end):
        endwithext = end
        if os.name == "nt":
            endwithext = f"{end}.exe"

        if end in ("3", ""):
            os.link(str(executable), str(tmpdir / f"python{endwithext}"))
        else:
            parent = executable.parent
            location = parent / f"python{endwithext}"
            if not location.exists():
                os.link(str(executable), str(location))
            paths.append(executable.parent)

    @contextmanager
    def configure(self, *versions, python3=None, python=False, mock_sys=False):
        tmpdir = None

        class Empty:
            pass

        before = os.environ.get("PATH", Empty)
        try:
            tmpdir = Path(
                tempfile.mkdtemp(
                    suffix=f'__INCLUDING__-{"_".join(str(v) for v in versions)}-python={python}-python3={python3}'
                )
            )
            paths = [tmpdir]

            link = lambda exe, *, end: self.link(tmpdir, paths, exe, end=end)

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

            if os.name == "nt":
                os.environ["PATH"] = ";".join(str(p) for p in paths)
            else:
                os.environ["PATH"] = ":".join(str(p) for p in paths)

            if mock_sys is not False:
                with mock.patch.object(sys, "executable", self.pythons[mock_sys]):
                    yield
            else:
                yield
        finally:
            if tmpdir is not None and tmpdir.exists():
                shutil.rmtree(tmpdir)
            if before is Empty:
                if "PATH" in os.environ:
                    del os.environ["PATH"]
            else:
                os.environ["PATH"] = before


def assertPythonVersion(python_exe, version):
    _, got = PythonHandler().version_for(python_exe, raise_error=True, without_patch=True)
    assert got == version, (got, version)


def write_script(func, args="", *, filename, exe=None, prepare_venv=False, decorator=None):
    script = dedent(inspect.getsource(func))

    if decorator is not None:
        decorator = dedent(inspect.getsource(decorator))

    with open(filename, "w") as fle:
        lines = [f"#!{exe or sys.executable}", "import sys"]

        if decorator is not None:
            lines.append(decorator)
            lines.append(f"@decorator({args})")
            lines.append(script)
        else:
            lines.append(script)
            lines.append(f"script({args})")

        fle.write("\n".join(lines))

    with open(filename) as fle:
        print(file=sys.stderr)
        print(f">>CONFTEST: {filename}\n{fle.read()}", file=sys.stderr)
        print("<<CONFTEST", file=sys.stderr)
        print(file=sys.stderr)

    os.chmod(filename, 0o755)

    if prepare_venv:
        cmd = str(filename)
        if os.name == "nt":
            cmd = [str(exe or sys.executable), str(filename)]
        subprocess.run(
            cmd,
            env={**os.environ, "VENVSTARTER_ONLY_MAKE_VENV": "1"},
            check=True,
        )


@contextmanager
def make_script(func, args="", exe=None, prepare_venv=False, decorator=None):
    directory = None
    try:
        directory = Path(tempfile.mkdtemp())
        location = directory / "starter"
        write_script(
            func,
            args=args,
            exe=exe,
            prepare_venv=prepare_venv,
            filename=location,
            decorator=decorator,
        )
        yield location
    finally:
        if directory and directory.exists():
            shutil.rmtree(directory)


def get_output(venvstarter_script_filename, *args):
    try:
        output = (
            subprocess.check_output(
                [str(q) for q in PythonHandler().with_shebang(venvstarter_script_filename, *args)],
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


class DirectoryCreator:
    def __init__(self):
        self.files = {}

    def add(self, *path, content, mode=0o644):
        self.files[path] = content
        if hasattr(self, "path"):
            self.write(path, content, mode=mode)

    def write(self, path, content, mode=0o644):
        location = self.path
        for part in path:
            location = location / part

        if not os.path.exists(location.parent):
            location.parent.mkdir()
        with open(location, "w") as fle:
            fle.write(dedent(content).strip())
        os.chmod(location, mode)

    def __enter__(self):
        if not hasattr(self, "path"):
            self.path = Path(tempfile.mkdtemp())
        for path, content in self.files.items():
            self.write(path, content)
        return self

    def __exit__(self, exc_typ, exc, tb):
        if hasattr(self, "path") and self.path.exists():
            shutil.rmtree(self.path)
            del self.path


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
        mv = Path(os.environ["TEST_VENVS"])
        if not mv.exists():
            mv.mkdir()
    else:
        global made_venvs
        made_venvs = Path(tempfile.mkdtemp())
        mv = made_venvs

    pythons = PythonsFinder(mv).find()
    pytest.helpers.register(get_output)
    pytest.helpers.register(make_script)
    pytest.helpers.register(write_script)
    pytest.helpers.register(DirectoryCreator, name="directory_creator")
    pytest.helpers.register(assertPythonVersion)

    pytest.helpers._registry["PATH"] = PATH(pythons)
    pytest.helpers._registry["pythons"] = pythons


def pytest_unconfigure(config):
    if made_venvs and made_venvs.exists():
        shutil.rmtree(made_venvs)
