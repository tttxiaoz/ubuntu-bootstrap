"""计划模型：选定任务 + 拓扑排序 + 运行时答案。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..platform.sys import TaskError
from .task import Task


@dataclass
class Step:
    task: Task
    answers: dict[str, Any] = field(default_factory=dict)  # Param.key -> 运行时答案
    include: bool = True                                    # 向导中用户可跳过


@dataclass
class Plan:
    steps: list[Step]
    force: bool = False
    dry_run: bool = False


def topo_sort(tasks: list[Task]) -> list[Task]:
    """按 depends_on 拓扑排序（稳定，依赖在前）。"""
    by_id = {t.meta.id: t for t in tasks}
    result: list[Task] = []
    state: dict[str, int] = {}  # 0 未访问 / 1 访问中 / 2 完成

    def visit(t: Task) -> None:
        sid = state.get(t.meta.id, 0)
        if sid == 2:
            return
        if sid == 1:
            raise TaskError(f"循环依赖: {t.meta.id}")
        state[t.meta.id] = 1
        for dep_id in t.meta.depends_on:
            dep = by_id.get(dep_id)
            if dep is not None:
                visit(dep)
        state[t.meta.id] = 2
        result.append(t)

    for t in tasks:
        visit(t)
    return result


def batch_plan(tasks: list[Task], *, force: bool = False, dry_run: bool = False) -> Plan:
    """非交互批量：全部纳入、无运行时答案（直接用 config 值）。"""
    ordered = topo_sort(tasks)
    steps = [Step(task=t) for t in ordered]
    return Plan(steps=steps, force=force, dry_run=dry_run)
