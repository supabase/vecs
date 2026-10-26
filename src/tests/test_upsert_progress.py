import sys
import types

import numpy as np
import pytest

import vecs


def _records(n: int, dim: int = 4):
    return [(f"vec{ix}", vec, {}) for ix, vec in enumerate(np.random.random((n, dim)))]


class _FakeBar:
    """Records tqdm calls so tests don't need a TTY or notebook."""

    instances = []

    def __init__(self, total=None, **_):
        self.total = total
        self.updates = []
        self.closed = False
        _FakeBar.instances.append(self)

    def update(self, n):
        self.updates.append(n)

    def close(self):
        self.closed = True


@pytest.fixture
def fake_tqdm(monkeypatch):
    _FakeBar.instances.clear()
    auto = types.ModuleType("tqdm.auto")
    auto.tqdm = _FakeBar
    pkg = types.ModuleType("tqdm")
    pkg.auto = auto
    monkeypatch.setitem(sys.modules, "tqdm", pkg)
    monkeypatch.setitem(sys.modules, "tqdm.auto", auto)
    return _FakeBar


def test_upsert_default_has_no_progress(client: vecs.Client, fake_tqdm) -> None:
    coll = client.get_or_create_collection(name="prog_default", dimension=4)
    coll.upsert(_records(10))
    assert fake_tqdm.instances == []
    assert len(coll) == 10


def test_upsert_progress_sized_reports_total(client: vecs.Client, fake_tqdm) -> None:
    coll = client.get_or_create_collection(name="prog_sized", dimension=4)
    coll.upsert(_records(1200), show_progress=True)
    (bar,) = fake_tqdm.instances
    assert bar.total == 1200
    assert bar.updates == [500, 500, 200]
    assert bar.closed
    assert len(coll) == 1200


def test_upsert_progress_generator_is_indeterminate(
    client: vecs.Client, fake_tqdm
) -> None:
    coll = client.get_or_create_collection(name="prog_gen", dimension=4)
    coll.upsert((r for r in _records(7)), show_progress=True)
    (bar,) = fake_tqdm.instances
    assert bar.total is None
    assert sum(bar.updates) == 7
    assert bar.closed


def test_upsert_progress_without_tqdm_raises(client: vecs.Client, monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "tqdm", None)
    monkeypatch.setitem(sys.modules, "tqdm.auto", None)
    coll = client.get_or_create_collection(name="prog_missing", dimension=4)
    with pytest.raises(ImportError, match="vecs\\[progress\\]"):
        coll.upsert(_records(3), show_progress=True)


def test_upsert_progress_closes_on_error(client: vecs.Client, fake_tqdm) -> None:
    coll = client.get_or_create_collection(name="prog_error", dimension=4)
    # the second chunk carries a 5-dimension vector, so its insert fails
    records = _records(500) + [("bad", np.random.random(5), {})]
    with pytest.raises(Exception):
        coll.upsert(records, show_progress=True)
    (bar,) = fake_tqdm.instances
    assert bar.updates == [500]
    assert bar.closed
