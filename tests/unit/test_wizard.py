"""ui.wizard.questions_for_task 过滤逻辑测试。"""

from __future__ import annotations

from bootstrap.config.schema import Param
from bootstrap.core.task import CheckResult, Task, TaskMeta
from bootstrap.ui.wizard import questions_for_task


def make_task(params):
    class T(Task):
        def check(self, ctx):
            return CheckResult(False)

        def run(self, ctx):
            pass

    t = T()
    t.meta = TaskMeta(id="x", name="x", description="", depends_on=(), params=tuple(params))
    return t


def test_questions_for_task_filters_interactive():
    t = make_task([
        Param("a", "choice", interactive=True),
        Param("b", "choice", interactive=False),
        Param("c", "choice", interactive=True),
    ])
    assert [p.key for p in questions_for_task(t)] == ["a", "c"]


def test_questions_for_task_defaults_interactive():
    t = make_task([Param("a", "choice")])
    assert len(questions_for_task(t)) == 1


def test_questions_for_task_no_params():
    t = make_task([])
    assert questions_for_task(t) == []
