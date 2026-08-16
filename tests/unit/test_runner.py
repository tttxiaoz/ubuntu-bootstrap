"""core.runner 执行引擎状态流转测试。"""

from __future__ import annotations

from bootstrap.config import Config
from bootstrap.core.plan import Plan, Step
from bootstrap.core.runner import Runner
from bootstrap.core.task import CheckResult, Task, TaskMeta


def _task(tid: str, done: bool, fail: bool = False) -> Task:
    class T(Task):
        def check(self, ctx):
            return CheckResult(done, "已配置" if done else "未配置")

        def run(self, ctx):
            ctx.log.log(f"run {tid}")
            if fail:
                raise RuntimeError("boom")

    t = T()
    t.meta = TaskMeta(id=tid, name=tid, description="", depends_on=(), params=())
    return t


def test_runner_skip_when_done(tmp_path):
    plan = Plan(steps=[Step(task=_task("a", done=True))], force=False)
    report = Runner(log_dir=str(tmp_path)).run(plan, Config({}))
    assert report.results[0].status == "skip"
    assert report.all_ok() is True


def test_runner_ok(tmp_path):
    plan = Plan(steps=[Step(task=_task("a", done=False))], force=False)
    report = Runner(log_dir=str(tmp_path)).run(plan, Config({}))
    assert report.results[0].status == "ok"


def test_runner_fail(tmp_path):
    plan = Plan(steps=[Step(task=_task("a", done=False, fail=True))], force=False)
    report = Runner(log_dir=str(tmp_path)).run(plan, Config({}))
    assert report.results[0].status == "fail"
    assert report.all_ok() is False


def test_runner_force_reruns_done_task(tmp_path):
    plan = Plan(steps=[Step(task=_task("a", done=True))], force=True)
    report = Runner(log_dir=str(tmp_path)).run(plan, Config({}))
    assert report.results[0].status == "ok"


def test_report_json(tmp_path):
    plan = Plan(steps=[Step(task=_task("a", done=False))], force=False)
    report = Runner(log_dir=str(tmp_path)).run(plan, Config({}))
    assert '"task": "a"' in report.to_json()
