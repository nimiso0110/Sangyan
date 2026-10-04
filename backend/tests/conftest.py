import pytest

from app import learn


@pytest.fixture(autouse=True)
def _isolated_learning_db(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARN_DB", str(tmp_path / "learn.db"))
    learn._inval()
    yield
    learn._inval()
