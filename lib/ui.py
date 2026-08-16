"""交互式菜单：curses 多选复选框（含状态列），无 TTY 时降级为数字输入。"""

from __future__ import annotations

import sys


def _status_of(task, cfg):
    """返回任务的 (已配置, 说明) 用于菜单状态显示。"""
    try:
        done, note = task.check(cfg, log=None)
    except Exception:
        done, note = False, "检测失败"
    return done, note


def select_tasks(tasks, cfg) -> list:
    """返回用户选中的任务列表；无 TTY 时降级为数字多选。"""
    if sys.stdout.isatty() and sys.stdin.isatty():
        try:
            return _curses_select(tasks, cfg)
        except Exception:
            # curses 初始化失败则降级
            pass
    return _plain_select(tasks, cfg)


def _curses_select(tasks, cfg) -> list:
    import curses

    return curses.wrapper(_CursesMenu(tasks, cfg).run)


class _CursesMenu:
    def __init__(self, tasks, cfg):
        self.tasks = tasks
        self.cfg = cfg
        self.selected = [False] * len(tasks)
        self.cursor = 0

    def run(self, stdscr) -> list:
        curses.curs_set(0)
        while True:
            self._draw(stdscr)
            key = stdscr.getch()
            n = len(self.tasks)
            if key in (curses.KEY_UP, ord("k")):
                self.cursor = (self.cursor - 1) % n
            elif key in (curses.KEY_DOWN, ord("j")):
                self.cursor = (self.cursor + 1) % n
            elif key in (ord(" "), ord("x")):
                self.selected[self.cursor] = not self.selected[self.cursor]
            elif key in (ord("a"),):
                self.selected = [True] * n
            elif key in (ord("n"),):
                self.selected = [False] * n
            elif key in (curses.KEY_ENTER, 10, 13):
                return [t for t, s in zip(self.tasks, self.selected) if s]
            elif key in (ord("q"), 27):
                return []

    def _draw(self, stdscr):
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        title = "Ubuntu 初始化工具 —— 空格选择 / a 全选 / n 全不选 / 回车执行 / q 退出"
        stdscr.addnstr(0, 0, title, w - 1)

        # 预计算状态，避免每帧重复跑 check（首次绘制时缓存）
        if not hasattr(self, "_status_cache"):
            self._status_cache = [_status_of(t, self.cfg) for t in self.tasks]

        start = 1
        for i, task in enumerate(self.tasks):
            if start >= h - 2:
                break
            done, note = self._status_cache[i]
            mark = "[x]" if self.selected[i] else "[ ]"
            status = "已配置" if done else "未配置"
            cursor = ">" if i == self.cursor else " "
            line = f"{cursor} {mark} {task.name}  [{status}]"
            stdscr.addnstr(start, 0, line, w - 1)
            start += 1
            if i == self.cursor and note:
                stdscr.addnstr(start, 2, f"    {task.description} — {note}", w - 3)
                start += 1

        selected_count = sum(self.selected)
        footer = f"已选 {selected_count}/{len(self.tasks)}"
        stdscr.addnstr(h - 1, 0, footer, w - 1)
        stdscr.refresh()


def _plain_select(tasks, cfg) -> list:
    print("Ubuntu 初始化工具（无 TTY 模式）")
    for i, task in enumerate(tasks):
        done, note = _status_of(task, cfg)
        status = "已配置" if done else "未配置"
        print(f"  {i + 1}. {task.name} [{status}] — {task.description}")
    print("输入要执行的任务编号（逗号分隔，如 1,3,5；all=全部；回车=取消）：")
    raw = input("> ").strip()
    if not raw:
        return []
    if raw.lower() == "all":
        return list(tasks)
    idxs = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            idx = int(part) - 1
        except ValueError:
            continue
        if 0 <= idx < len(tasks):
            idxs.append(idx)
    return [tasks[i] for i in idxs]
