"""任务执行器：依赖拓扑排序 + 顺序执行 + 结果摘要。"""

from __future__ import annotations

import datetime
import os
import sys

from . import tui, utils
from .tasks import REGISTRY


def topo_sort(tasks: list) -> list:
    """按 depends_on 拓扑排序（稳定，依赖在前）。"""
    by_id = {t.id: t for t in tasks}
    result: list = []
    state: dict = {}  # id -> 0 未访问 / 1 访问中 / 2 完成

    def visit(task):
        sid = state.get(task.id, 0)
        if sid == 2:
            return
        if sid == 1:
            raise utils.TaskError(f"循环依赖: {task.id}")
        state[task.id] = 1
        for dep_id in task.depends_on:
            dep = by_id.get(dep_id)
            if dep is not None:
                visit(dep)
        state[task.id] = 2
        result.append(task)

    for t in tasks:
        visit(t)
    return result


class Logger:
    """同时写终端与日志文件。"""

    def __init__(self, log_dir: str):
        os.makedirs(log_dir, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.path = os.path.join(log_dir, f"{stamp}.log")
        self._fh = open(self.path, "a", encoding="utf-8")

    def __call__(self, message: str = "", style: str | None = None) -> None:
        # 终端按 style 上色，日志文件始终写纯文本（不含 ANSI 码）
        if style and sys.stdout.isatty():
            print(tui.paint(message, style), flush=True)
        else:
            print(message, flush=True)
        self._fh.write(message + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


def run_one(task, cfg, logger, *, force: bool = False) -> str:
    """执行单个任务，返回 "ok" | "skip" | "fail"。"""
    done, note = task.check(cfg, log=None)
    if done and not force:
        logger(f"⏭ 跳过 {task.name}（{note}）", style="yellow")
        return "skip"
    logger(f"▶ 执行 {task.name} ...", style="blue")
    try:
        task.run(cfg, log=logger)
        logger(f"✅ {task.name} 完成", style="green")
        return "ok"
    except utils.TaskError as exc:
        logger(f"❌ {task.name} 失败: {exc}", style="red")
        return "fail"
    except Exception as exc:  # noqa: BLE001 - 兜底，避免单个任务意外异常中断整批
        logger(f"❌ {task.name} 意外失败: {exc!r}", style="red")
        return "fail"


def run_tasks(tasks: list, cfg, *, force: bool = False, dry_run: bool = False,
              log_dir: str = "logs") -> dict:
    """执行选中任务，返回 {task.id: status}。"""
    ordered = topo_sort(tasks)
    logger = Logger(log_dir)
    results: dict = {}
    try:
        for task in ordered:
            if dry_run:
                done, note = task.check(cfg, log=None)
                logger(f"[DRY-RUN] {task.id}: {'已配置' if done else '待执行'}（{note}）")
                continue
            results[task.id] = run_one(task, cfg, logger, force=force)
    finally:
        logger.close()
    return results


def print_summary(results: dict) -> None:
    by_id = {t.id: t for t in REGISTRY}
    rows = []
    for tid, status in results.items():
        name = by_id.get(tid, None)
        name = name.name if name else tid
        mark = {"ok": "✅", "skip": "⏭", "fail": "❌"}.get(status, "?")
        rows.append((name, mark))
    tui.print_summary_table(rows)
    ok = sum(1 for s in results.values() if s == "ok")
    skip = sum(1 for s in results.values() if s == "skip")
    fail = sum(1 for s in results.values() if s == "fail")
    summary = f"\n成功 {ok} · 跳过 {skip} · 失败 {fail}"
    if tui.rich_available():
        from rich.console import Console
        Console().print(summary)
    else:
        print(summary)
