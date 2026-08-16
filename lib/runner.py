"""任务执行器：依赖拓扑排序 + 顺序执行 + 结果摘要。"""

from __future__ import annotations

import datetime
import os
import sys

from . import utils
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

    def __call__(self, message: str = "") -> None:
        print(message, flush=True)
        self._fh.write(message + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


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

            done, note = task.check(cfg, log=None)
            if done and not force:
                logger(f"⏭ 跳过 {task.name}（{note}）")
                results[task.id] = "skip"
                continue

            logger(f"▶ 执行 {task.name} ...")
            try:
                task.run(cfg, log=logger)
                results[task.id] = "ok"
                logger(f"✅ {task.name} 完成")
            except utils.TaskError as exc:
                results[task.id] = "fail"
                logger(f"❌ {task.name} 失败: {exc}")
    finally:
        logger.close()
    return results


def print_summary(results: dict) -> None:
    by_id = {t.id: t for t in REGISTRY}
    print("\n========== 执行结果 ==========")
    for tid, status in results.items():
        name = by_id.get(tid, None)
        name = name.name if name else tid
        mark = {"ok": "✅", "skip": "⏭", "fail": "❌"}.get(status, "?")
        print(f"{mark} {name}")
    ok = sum(1 for s in results.values() if s == "ok")
    skip = sum(1 for s in results.values() if s == "skip")
    fail = sum(1 for s in results.values() if s == "fail")
    print(f"\n成功 {ok} · 跳过 {skip} · 失败 {fail}")
