"""执行引擎：按 Plan 顺序执行任务，产出 Report。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from ..config import Config
from ..config.schema import _set_path
from ..platform.apt import AptManager
from ..platform.sys import TaskError
from .log import Logger
from .plan import Plan
from .task import Context

Status = Literal["ok", "skip", "fail"]


@dataclass
class TaskResult:
    task_id: str
    status: Status
    note: str = ""


@dataclass
class Report:
    results: list[TaskResult] = field(default_factory=list)

    def all_ok(self) -> bool:
        return all(r.status != "fail" for r in self.results)

    def counts(self) -> tuple[int, int, int]:
        ok = sum(1 for r in self.results if r.status == "ok")
        skip = sum(1 for r in self.results if r.status == "skip")
        fail = sum(1 for r in self.results if r.status == "fail")
        return ok, skip, fail

    def summary(self) -> str:
        ok, skip, fail = self.counts()
        return f"成功 {ok} · 跳过 {skip} · 失败 {fail}"

    def to_json(self) -> str:
        payload = [{"task": r.task_id, "status": r.status, "note": r.note}
                   for r in self.results]
        return json.dumps(payload, ensure_ascii=False, indent=2)


class Runner:
    """执行 Plan：每个 include 的 step 依次 check → run，结果进 Report。"""

    def __init__(self, log_dir: str = "logs") -> None:
        self.log_dir = log_dir

    def run(self, plan: Plan, config: Config) -> Report:
        logger = Logger(self.log_dir)
        apt = AptManager()
        report = Report()
        try:
            for step in plan.steps:
                if not step.include:
                    report.results.append(
                        TaskResult(step.task.meta.id, "skip", "向导中跳过"))
                    continue
                step_config = _step_config(config, step.answers)
                ctx = Context(config=step_config, log=logger, apt=apt, force=plan.force)
                if plan.dry_run:
                    res = step.task.check(ctx)
                    logger.log(f"[DRY-RUN] {step.task.meta.id}: "
                               f"{'已配置' if res.done else '待执行'}（{res.note}）")
                    continue
                status, note = self._run_one(step.task, ctx)
                report.results.append(TaskResult(step.task.meta.id, status, note))
        finally:
            logger.close()
        return report

    @staticmethod
    def _run_one(task, ctx: Context) -> tuple[Status, str]:
        res = task.check(ctx)
        done, note = res.done, res.note
        if done and not ctx.force:
            ctx.log(f"⏭ 跳过 {task.meta.name}（{note}）", style="yellow")
            return "skip", note
        ctx.log(f"▶ 执行 {task.meta.name} ...", style="blue")
        try:
            task.run(ctx)
            ctx.log(f"✅ {task.meta.name} 完成", style="green")
            return "ok", ""
        except TaskError as exc:
            ctx.log(f"❌ {task.meta.name} 失败: {exc}", style="red")
            return "fail", str(exc)
        except Exception as exc:  # noqa: BLE001 - 兜底，避免单个任务意外异常中断整批
            ctx.log(f"❌ {task.meta.name} 意外失败: {exc!r}", style="red")
            return "fail", repr(exc)


def _step_config(base: Config, answers: dict[str, Any]) -> Config:
    """把运行时答案覆盖到基础配置上，得到该步骤的有效配置。"""
    if not answers:
        return base
    data = base.as_dict()
    for key, value in answers.items():
        _set_path(data, key, value)
    return Config(data)
