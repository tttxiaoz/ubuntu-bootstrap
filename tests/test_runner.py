"""runner.topo_sort 拓扑排序测试。"""

from __future__ import annotations

import pytest

from lib import utils
from lib.runner import topo_sort
from lib.tasks.base import Task


def make_task(tid: str, deps: tuple = ()) -> Task:
    t = Task()
    t.id = tid
    t.name = tid
    t.depends_on = list(deps)
    return t


def test_empty():
    assert topo_sort([]) == []


def test_dependency_order():
    a = make_task("a", deps=("b",))
    b = make_task("b")
    ordered = topo_sort([a, b])
    assert ordered.index(b) < ordered.index(a)


def test_chain():
    a = make_task("a", deps=("b",))
    b = make_task("b", deps=("c",))
    c = make_task("c")
    ordered = topo_sort([a, b, c])
    assert ordered.index(c) < ordered.index(b) < ordered.index(a)


def test_stable_for_independent():
    a, b, c = make_task("a"), make_task("b"), make_task("c")
    ordered = topo_sort([c, a, b])
    assert ordered == [c, a, b]


def test_cycle_raises():
    a = make_task("a", deps=("b",))
    b = make_task("b", deps=("a",))
    with pytest.raises(utils.TaskError):
        topo_sort([a, b])


def test_unknown_dependency_ignored():
    a = make_task("a", deps=("nonexistent",))
    ordered = topo_sort([a])
    assert ordered == [a]
