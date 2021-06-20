import pytest
import json
import os

this_dir = os.path.dirname(__file__)


class Pythons:
    def __init__(self, locations):
        self.locations = locations

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


@pytest.fixture(autouse=True)
def pythons():
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
        pythons[k] = os.path.expanduser(pythons[k])
        if not os.path.isfile(pythons[k]):
            pytest.exit(f"Entry for {k} ({pythons[k]}) is not a file")

    return Pythons(pythons)
