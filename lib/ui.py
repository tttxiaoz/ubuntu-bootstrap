"""交互式逐步执行向导。

流程：逐个任务确认 →（可选）用 gum 选择该任务的配置项 → 立即执行 → 下一项。
优先使用 gum（Charmbracelet）提供漂亮 TUI；gum 缺失或无 TTY 时降级为纯文本逐项询问。
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

    优先使用 gum（Charmbracelet）提供漂亮 TUI；gum 缺失或无 TTY 时降级文本模式。
    """
    if sys.stdout.isatty() and sys.stdin.isatty():
        from . import gum

        if gum.ensure_gum(cfg):
            return _gum_run(tasks, cfg, force, log_dir)
        # ensure_gum 失败时已打印降级说明
    return _plain_run(tasks, cfg, force, log_dir)


# --------------------------------------------------------------------------
# gum 向导
# --------------------------------------------------------------------------

def _gum_run(tasks, cfg, force, log_dir) -> dict:
    from . import gum, runner

    logger = runner.Logger(log_dir)
    ordered = runner.topo_sort(tasks)
    results: dict = {}
    try:
        _banner(gum)

        for i, task in enumerate(ordered):
            done, note = _status_of(task, cfg)

            # 1) 任务确认（默认：未配置执行，已配置跳过）
            status_tag = "已配置" if done else "未配置"
            gum.style(
                f"\n[{i + 1}/{len(ordered)}] {task.name}",
                foreground="212", bold=True,
            )
            gum.style(f"  {task.description}   （当前状态：{status_tag}）",
                      foreground="240")
            if note:
                gum.style(f"  {note}", foreground="244")

            want = gum.confirm(
                f"{task.name} —— 是否执行？",
                default=not done,
            )
            if not want:
                results[task.id] = "skip"
                gum.style("  ⏭ 已跳过", foreground="214")
                continue

            # 2) 配置项
            for q in questions_for_task(cfg, task.id):
                _ask_question(gum, cfg, q)

            # 3) 执行
            gum.style(f"\n▶ 执行 {task.name} ...", foreground="39", bold=True)
            status = runner.run_one(task, cfg, logger, force=force)
            results[task.id] = status

            color = {"ok": "40", "skip": "214", "fail": "196"}.get(status, "250")
            mark = {"ok": "✅", "skip": "⏭", "fail": "❌"}.get(status, "?")
            gum.style(f"{mark} {task.name}", foreground=color, bold=True)
    finally:
        logger.close()
    runner.print_summary(results)
    return results


def _banner(gum) -> None:
    gum.style(
        "\n  Ubuntu 新机初始化工具  ",
        foreground="51", bold=True, padding="1 2", border="rounded",
        border_foreground="51",
    )


def _ask_question(gum, cfg, q) -> None:
    key = q["config_key"]
    if q["type"] == "choice":
        opts = resolve_options(cfg, q)
        cur = getattr(cfg, key, None)
        value = gum.choose(opts, header=f"{q['name']}（当前：{cur}）",
                           selected=cur, limit=1)
        if value is not None:
            setattr(cfg, key, value)
    else:  # bool
        cur = getattr(cfg, key, "yes") == "yes"
        value = gum.confirm(f"{q['name']}？", default=cur)
        setattr(cfg, key, "yes" if value else "no")


# --------------------------------------------------------------------------
# 无 TTY 降级：逐项询问
# --------------------------------------------------------------------------

def _plain_run(tasks, cfg, force, log_dir) -> dict:
    from . import runner

    logger = runner.Logger(log_dir)
    ordered = runner.topo_sort(tasks)
    results: dict = {}

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
            if q["type"] == "choice":
                cur = getattr(cfg, q["config_key"], None)
                for i, o in enumerate(opts):
                    mark = ">" if o == cur else " "
                    print(f"  {mark} {i + 1}. {o}")
                raw = input(f"{q['name']} [1-{len(opts)}] ").strip()
                if raw.isdigit() and 1 <= int(raw) <= len(opts):
                    setattr(cfg, q["config_key"], opts[int(raw) - 1])
            else:
                cur = getattr(cfg, q["config_key"], "yes") == "yes"
                raw = input(f"{q['name']} [y/n，默认 {'y' if cur else 'n'}] ").strip().lower()
                if raw:
                    setattr(cfg, q["config_key"], "yes" if raw in ("y", "yes") else "no")

        results[t.id] = runner.run_one(t, cfg, logger, force=force)
        print()

    logger.close()
    runner.print_summary(results)
    return results
