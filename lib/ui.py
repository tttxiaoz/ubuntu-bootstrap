"""交互式逐步执行向导。

流程：逐个任务确认 →（可选）选择该任务的配置项 → 立即执行 → 下一项。
优先使用 rich（彩色展示）+ questionary（交互选择）提供漂亮 TUI；
依赖缺失或无 TTY 时逐级降级为 ANSI 纯文本逐项询问。
"""

from __future__ import annotations

import sys


# --------------------------------------------------------------------------
# QUESTIONS 解析（模块级，便于单测）
# --------------------------------------------------------------------------

def questions_for_task(cfg, task_id: str) -> list:
    """返回某任务关联的、interactive 开启的配置项。"""
    qs = getattr(cfg, "QUESTIONS", []) or []
    return [q for q in qs
            if q.get("task") == task_id and q.get("interactive", True)]


def resolve_options(cfg, q: dict) -> list:
    """解析 question 的候选列表（支持 '@' 引用 config 变量）。"""
    opts = q.get("options", [])
    if isinstance(opts, str) and opts.startswith("@"):
        val = getattr(cfg, opts[1:], None)
        if isinstance(val, dict):
            return list(val.keys())
        if isinstance(val, (list, tuple)):
            return list(val)
        return []
    return list(opts)


def _status_of(task, cfg):
    try:
        done, note = task.check(cfg, log=None)
    except Exception:
        done, note = False, "检测失败"
    return done, note


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------

def run_wizard(tasks, cfg, *, force: bool = False, log_dir: str = "logs") -> dict:
    """逐步执行向导，返回 {task.id: status}。

    TTY 下优先用 rich + questionary 提供漂亮 TUI（缺失自动 pip 安装、逐级降级）；
    无 TTY 时降级为纯文本逐项询问。
    """
    if sys.stdout.isatty() and sys.stdin.isatty():
        from . import tui

        tui.ensure_deps(cfg)
        return _tui_run(tasks, cfg, force, log_dir)
    return _plain_run(tasks, cfg, force, log_dir)


# --------------------------------------------------------------------------
# rich + questionary 向导（内部逐级降级）
# --------------------------------------------------------------------------

def _tui_run(tasks, cfg, force, log_dir) -> dict:
    from . import runner, tui

    logger = runner.Logger(log_dir)
    ordered = runner.topo_sort(tasks)
    results: dict = {}
    try:
        tui.banner("Ubuntu 新机初始化工具")

        for i, task in enumerate(ordered):
            done, note = _status_of(task, cfg)

            # 1) 任务确认（默认：未配置执行，已配置跳过）
            status_tag = "已配置" if done else "未配置"
            tui.task_header(i + 1, len(ordered), task.name,
                            task.description, status_tag, note)

            want = tui.confirm(f"{task.name} —— 是否执行？", default=not done)
            if not want:
                results[task.id] = "skip"
                tui.status_line("⏭", task.name, "skip")
                continue

            # 2) 配置项
            for q in questions_for_task(cfg, task.id):
                _ask_question_tui(tui, cfg, q)

            # 3) 执行
            tui.heading(f"▶ 执行 {task.name} ...")
            status = runner.run_one(task, cfg, logger, force=force)
            results[task.id] = status

            mark = {"ok": "✅", "skip": "⏭", "fail": "❌"}.get(status, "?")
            tui.status_line(mark, task.name, status)
    finally:
        logger.close()
    runner.print_summary(results)
    return results


def _ask_question_tui(tui, cfg, q) -> None:
    key = q["config_key"]
    qtype = q["type"]
    if qtype == "choice":
        opts = resolve_options(cfg, q)
        cur = getattr(cfg, key, None)
        value = tui.choose(opts, header=f"{q['name']}（当前：{cur}）", selected=cur)
        if value is not None:
            setattr(cfg, key, value)
    elif qtype == "bool":
        cur = getattr(cfg, key, "yes") == "yes"
        value = tui.confirm(f"{q['name']}？", default=cur)
        setattr(cfg, key, "yes" if value else "no")
    elif qtype == "multi":
        opts = resolve_options(cfg, q)
        cur = getattr(cfg, key, None) or []
        value = tui.multiselect(opts, header=q["name"], selected=cur)
        if value:
            setattr(cfg, key, value)
    elif qtype == "password":
        value = tui.password(q["name"])
        if value is not None:
            setattr(cfg, key, value)


# --------------------------------------------------------------------------
# 无 TTY 降级：逐项询问
# --------------------------------------------------------------------------

def _plain_run(tasks, cfg, force, log_dir) -> dict:
    from . import runner, tui

    logger = runner.Logger(log_dir)
    ordered = runner.topo_sort(tasks)
    results: dict = {}

    try:
        print("Ubuntu 初始化工具（无 TTY 模式）——逐步确认，回车=推荐值")
        for t in ordered:
            done, note = _status_of(t, cfg)
            default = "n" if done else "y"
            label = "跳过（已配置）" if done else "执行"
            hint = "[Y/n]" if not done else "[y/N]"
            try:
                ans = input(f"[{label}] {t.name} — {t.description}  {hint} ").strip().lower()
            except EOFError:
                ans = ""
            want = (ans in ("", "y", "yes")) if default == "y" else (ans in ("y", "yes"))
            if not want:
                results[t.id] = "skip"
                continue

            # 配置项
            for q in questions_for_task(cfg, t.id):
                opts = resolve_options(cfg, q)
                qtype = q["type"]
                if qtype == "choice":
                    cur = getattr(cfg, q["config_key"], None)
                    for i, o in enumerate(opts):
                        mark = ">" if o == cur else " "
                        print(f"  {mark} {i + 1}. {o}")
                    raw = input(f"{q['name']} [1-{len(opts)}] ").strip()
                    if raw.isdigit() and 1 <= int(raw) <= len(opts):
                        setattr(cfg, q["config_key"], opts[int(raw) - 1])
                elif qtype == "bool":
                    cur = getattr(cfg, q["config_key"], "yes") == "yes"
                    raw = input(f"{q['name']} [y/n，默认 {'y' if cur else 'n'}] ").strip().lower()
                    if raw:
                        setattr(cfg, q["config_key"], "yes" if raw in ("y", "yes") else "no")
                elif qtype == "multi":
                    cur = getattr(cfg, q["config_key"], None) or []
                    preselect = list(cur) if cur else list(opts)
                    for i, o in enumerate(opts):
                        mark = "x" if o in preselect else " "
                        print(f"  {mark} {i + 1}. {o}")
                    raw = input(f"{q['name']} 多选 [逗号分隔，回车=全选] ").strip()
                    if raw:
                        idxs = [int(x) for x in raw.replace(",", " ").split() if x.isdigit()]
                        setattr(cfg, q["config_key"],
                                [opts[i - 1] for i in idxs if 1 <= i <= len(opts)])
                elif qtype == "password":
                    value = tui.password(q["name"])
                    if value is not None:
                        setattr(cfg, q["config_key"], value)

            results[t.id] = runner.run_one(t, cfg, logger, force=force)
            print()
    finally:
        logger.close()
    runner.print_summary(results)
    return results
