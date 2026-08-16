"""交互式向导：确认任务 → 问参数 → 产出 Plan（不执行）。

只做「选什么、怎么答」，执行完全交给 Runner。tui 原语自身逐级降级
（rich/questionary → ANSI 纯文本），因此无需两套向导逻辑。
"""

from __future__ import annotations

from typing import Any

from ..config.schema import Param
from ..core.plan import Plan, Step, topo_sort
from ..core.task import Context, Task
from ..platform.apt import AptManager
from . import tui


def build_plan(selected: list[Task], config, *, force: bool = False) -> Plan:
    """逐步向导：逐个任务确认 → 问其交互参数 → 收集 answers/include → 返回 Plan。"""
    tui.ensure_deps(config)
    tui.banner("Ubuntu 新机初始化工具")
    ordered = topo_sort(selected)
    steps: list[Step] = []
    for i, task in enumerate(ordered):
        done, note = _status(task, config)
        status_tag = "已配置" if done else "未配置"
        tui.task_header(i + 1, len(ordered), task.meta.name,
                        task.meta.description, status_tag, note)
        want = tui.confirm(f"{task.meta.name} —— 是否执行？", default=not done)
        answers: dict[str, Any] = {}
        if want:
            for param in questions_for_task(task):
                answers[param.key] = _ask_param(config, param)
        steps.append(Step(task=task, answers=answers, include=want))
    return Plan(steps=steps, force=force)


def questions_for_task(task: Task) -> list[Param]:
    """返回任务关联的、interactive 开启的参数声明。"""
    return [p for p in task.meta.params if p.interactive]


def _ask_param(config, param: Param) -> Any:
    """询问单个参数，返回新值；取消则回退当前值。"""
    if param.type == "choice":
        opts = list(param.resolve_choices(config.as_dict()))
        cur = config.get(param.key)
        value = tui.choose(opts, header=f"{param.label}（当前：{cur}）", selected=cur)
        return value if value is not None else cur
    if param.type == "bool":
        cur = config.get(param.key)
        return tui.confirm(f"{param.label}？", default=bool(cur))
    if param.type == "multi":
        opts = list(param.resolve_choices(config.as_dict()))
        cur = config.get(param.key) or []
        return tui.multiselect(opts, header=param.label, selected=cur)
    if param.type == "password":
        value = tui.password(param.label)
        return value if value is not None else ""
    # str：纯文本输入（当前无此类交互项，保留扩展）
    try:
        raw = input(f"{param.label} [回车=当前 {config.get(param.key)}]: ").strip()
    except EOFError:
        raw = ""
    return raw or config.get(param.key)


def _status(task: Task, config) -> tuple[bool, str]:
    ctx = Context(config=config, log=None, apt=AptManager())
    try:
        res = task.check(ctx)
    except Exception:
        return False, "检测失败"
    return res.done, res.note
