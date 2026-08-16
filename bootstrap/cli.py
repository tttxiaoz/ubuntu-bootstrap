"""命令行入口。"""

from __future__ import annotations

import argparse
import os
import sys

from .config import load_config
from .core.plan import batch_plan
from .core.runner import Report, Runner
from .core.task import CheckResult, Context, Registry
from .platform.apt import AptManager
from .ui import tui
from .ui.wizard import build_plan

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ensure_root() -> None:
    if os.geteuid() == 0:
        return
    print("需要 root 权限，正在通过 sudo 重新执行...")
    os.execvp("sudo", ["sudo", sys.executable, *sys.argv])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ubuntu 新机初始化工具")
    parser.add_argument("--all", action="store_true", help="执行全部任务")
    parser.add_argument("--only", metavar="IDS", help="仅执行指定任务（逗号分隔 id）")
    parser.add_argument("--exclude", metavar="IDS", help="排除指定任务（逗号分隔 id）")
    parser.add_argument("--list", action="store_true", help="列出任务及状态")
    parser.add_argument("--dry-run", action="store_true", help="仅打印执行顺序，不实际执行")
    parser.add_argument("--force", action="store_true", help="强制重跑已配置任务")
    parser.add_argument("--yes", action="store_true", help="跳过执行前确认")
    parser.add_argument("--verbose", action="store_true", help="更详细的日志")
    return parser.parse_args()


def select_tasks(args) -> list:
    if args.all:
        tasks = Registry.all()
    elif args.only:
        ids = [s.strip() for s in args.only.split(",") if s.strip()]
        unknown = [i for i in ids if i not in Registry.ids()]
        if unknown:
            print(f"未知任务 id: {', '.join(unknown)}")
            sys.exit(1)
        tasks = [Registry.get(i) for i in ids]
    else:
        tasks = Registry.all()
    if args.exclude:
        excl = {s.strip() for s in args.exclude.split(",") if s.strip()}
        tasks = [t for t in tasks if t.meta.id not in excl]
    return tasks


def list_tasks(config) -> None:
    print("可用任务：")
    apt = AptManager()
    for t in Registry.all():
        ctx = Context(config=config, log=None, apt=apt)
        try:
            res = t.check(ctx)
        except Exception:
            res = CheckResult(False, "检测失败")
        status = "已配置" if res.done else "未配置"
        print(f"  {t.meta.id:16} [{status}] {t.meta.name} — {res.note}")
        for p in t.meta.params:
            if p.interactive:
                cur = config.get(p.key)
                print(f"      · {p.label} = {cur}")


def _confirm_batch(plan) -> None:
    print("将执行以下任务：")
    for step in plan.steps:
        print(f"  - {step.task.meta.name}（{step.task.meta.id}）")
    if sys.stdin.isatty():
        try:
            ans = input("\n确认执行？[y/N] ").strip().lower()
        except EOFError:
            ans = ""
        if ans not in ("y", "yes"):
            print("已取消。")
            sys.exit(0)
    else:
        print("（非交互终端，自动确认执行；如需静默输出可加 --yes）")


def _print_summary(report: Report) -> None:
    by_id = {t.meta.id: t.meta.name for t in Registry.all()}
    rows = [(by_id.get(r.task_id, r.task_id),
             {"ok": "✅", "skip": "⏭", "fail": "❌"}.get(r.status, "?"))
            for r in report.results]
    tui.print_summary_table(rows)
    ok, skip, fail = report.counts()
    summary = f"\n成功 {ok} · 跳过 {skip} · 失败 {fail}"
    if tui.rich_available():
        from rich.console import Console
        Console().print(summary)
    else:
        print(summary)


def main() -> int:
    args = parse_args()
    ensure_root()

    from . import tasks  # noqa: F401  触发任务注册
    config = load_config()

    if args.list:
        list_tasks(config)
        return 0

    selected = select_tasks(args)

    if args.all or args.only:
        plan = batch_plan(selected, force=args.force, dry_run=args.dry_run)
        if not args.dry_run and not args.yes:
            _confirm_batch(plan)
    else:
        # 交互向导：需要 TTY
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            print("无交互终端且未指定 --all/--only/--list，打印帮助。")
            return 1
        plan = build_plan(selected, config, force=args.force)

    report = Runner(log_dir=os.path.join(BASE_DIR, "logs")).run(plan, config)
    if not args.dry_run:
        _print_summary(report)
    return 0 if report.all_ok() else 1
