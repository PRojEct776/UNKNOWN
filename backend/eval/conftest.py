import json
import pathlib
import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "eval: end-to-end evaluation tests")


@pytest.fixture(scope="session")
def halluc_set():
    path = pathlib.Path(__file__).parent / "halluc_set.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
