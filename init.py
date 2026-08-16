#!/usr/bin/env python3
"""Ubuntu 新机初始化工具入口。

用法：
  sudo python3 init.py            # 交互式多选菜单
  sudo python3 init.py --all      # 执行全部任务
  sudo python3 init.py --only zsh,nvim   # 仅执行指定任务
  sudo python3 init.py --list     # 列出任务及当前状态
  sudo python3 init.py --dry-run --all  # 打印执行顺序，不实际执行
  sudo python3 init.py --force --all    # 强制重跑（忽略幂等判断）
  sudo python3 init.py --yes --all      # 跳过执行前确认
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from lib import runner, ui, utils  # noqa: E402
from lib.tasks import REGISTRY, TASKS  # noqa: E402


def ensure_root() -> None:
    if os.geteuid() == 0:
        return
    print("需要 root 权限，正在通过 sudo 重新执行...")
    os.execvp("sudo", ["sudo", sys.executable, *sys.argv])


def _chown_to_sudo_user(path: str) -> None:
    """把 root 生成的文件属主改回真实调用者（sudo 后默认属主是 root）。"""
    user = os.environ.get("SUDO_USER")
    if not user or user == "root":
        return
    try:
        shutil.chown(path, user=user)
    except (OSError, LookupError):
        pass


def load_config():
    """加载 config.py；缺失时从 config.example.py 复制并提示。"""
    cfg_path = os.path.join(BASE_DIR, "config.py")
    example_path = os.path.join(BASE_DIR, "config.example.py")
    if not os.path.exists(cfg_path):
        shutil.copyfile(example_path, cfg_path)
        _chown_to_sudo_user(cfg_path)
        print(f"已生成默认配置 {cfg_path}（源自 config.example.py），可按需修改后重跑。")
        print()
    import importlib.util

    spec = importlib.util.spec_from_file_location("config", cfg_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # 从 example 补齐缺失的常量（兼容旧 config.py，保留用户已改的值）
    example_spec = importlib.util.spec_from_file_location("_config_example", example_path)
    example = importlib.util.module_from_spec(example_spec)
    example_spec.loader.exec_module(example)
    for key in dir(example):
        if key.isupper() and not hasattr(module, key):
            setattr(module, key, getattr(example, key))

    return module


def list_tasks(cfg) -> None:
    print("可用任务：")
    for t in REGISTRY:
        done, note = t.check(cfg, log=None)
        status = "已配置" if done else "未配置"
        print(f"  {t.id:16} [{status}] {t.name} — {note}")
        # 打印该任务的交互配置项当前值
        qs = ui.questions_for_task(cfg, t.id)
        for q in qs:
            cur = getattr(cfg, q["config_key"], None)
            print(f"      · {q['name']} = {cur}")


def select_tasks_from_args(args, cfg):
    """返回 (tasks, interactive)。interactive=True 表示走逐步向导。"""
    if args.all:
        return list(REGISTRY), False
    if args.only:
        ids = [s.strip() for s in args.only.split(",") if s.strip()]
        unknown = [i for i in ids if i not in TASKS]
        if unknown:
            print(f"未知任务 id: {', '.join(unknown)}")
            sys.exit(1)
        return [TASKS[i] for i in ids], False
    return list(REGISTRY), True


def main() -> int:
    parser = argparse.ArgumentParser(description="Ubuntu 新机初始化工具")
    parser.add_argument("--all", action="store_true", help="执行全部任务")
    parser.add_argument("--only", metavar="IDS", help="仅执行指定任务（逗号分隔 id）")
    parser.add_argument("--list", action="store_true", help="列出任务及状态")
    parser.add_argument("--dry-run", action="store_true", help="仅打印执行顺序，不实际执行")
    parser.add_argument("--force", action="store_true", help="强制重跑已配置任务")
    parser.add_argument("--yes", action="store_true", help="跳过执行前确认")
    args = parser.parse_args()

    ensure_root()

    # 无 TTY 但也没给任务参数时，提示用法
    if not (args.all or args.only or args.list) and not sys.stdin.isatty():
        parser.print_help()
        return 1

    cfg = load_config()

    if args.list:
        list_tasks(cfg)
        return 0

    tasks, interactive = select_tasks_from_args(args, cfg)

    if interactive:
        # 逐步执行向导（内含执行与确认）
        ui.run_wizard(tasks, cfg, force=args.force,
                      log_dir=os.path.join(BASE_DIR, "logs"))
        return 0

    if not tasks:
        print("未选择任何任务，退出。")
        return 0

    # 命令行参数（--all/--only）批量执行，这里打印清单并二次确认
    if not args.dry_run and not args.yes:
        ordered = runner.topo_sort(tasks)
        print("将执行以下任务：")
        for t in ordered:
            print(f"  - {t.name}（{t.id}）")
        if sys.stdin.isatty():
            try:
                ans = input("\n确认执行？[y/N] ").strip().lower()
            except EOFError:
                ans = ""
            if ans not in ("y", "yes"):
                print("已取消。")
                return 0
        else:
            print("（非交互终端，自动确认执行；如需静默输出可加 --yes）")

    results = runner.run_tasks(tasks, cfg, force=args.force, dry_run=args.dry_run,
                               log_dir=os.path.join(BASE_DIR, "logs"))
    if not args.dry_run:
        runner.print_summary(results)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断。")
        sys.exit(130)
