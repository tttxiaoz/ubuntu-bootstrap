"""交互式向导：curses 逐步展示每个配置项，启用/跳过 + 最后汇总确认。

无 TTY 时降级为纯文本逐项询问。
"""

from __future__ import annotations

import sys


def _status_of(task, cfg):
    """返回任务的 (已配置, 说明)。"""
    try:
        done, note = task.check(cfg, log=None)
    except Exception:
        done, note = False, "检测失败"
    return done, note


def select_tasks(tasks, cfg) -> list:
    """运行向导，返回用户最终选中的任务列表；取消返回空列表。

    向导内部已包含最后的汇总确认，调用方无需再次确认。
    """
    if sys.stdout.isatty() and sys.stdin.isatty():
        try:
            return _wizard_select(tasks, cfg)
        except Exception:
            pass
    return _plain_select(tasks, cfg)


# --------------------------------------------------------------------------
# curses 向导
# --------------------------------------------------------------------------

def _wizard_select(tasks, cfg) -> list:
    import curses

    return curses.wrapper(_Wizard(tasks, cfg).run)


class _Wizard:
    """逐步向导：一屏一个任务，最后汇总确认。"""

    def __init__(self, tasks, cfg):
        self.tasks = tasks
        self.cfg = cfg
        # 预计算状态，避免每帧重复跑 check
        self.statuses = [_status_of(t, cfg) for t in tasks]
        # 默认：已配置的跳过，未配置的启用
        self.enabled = [not done for done, _ in self.statuses]
        self.index = 0
        self.stage = "task"  # "task" | "review"
        self._colors = False

    # ---- 主循环 ----

    def run(self, stdscr) -> list:
        curses.curs_set(0)
        self._init_colors()
        while True:
            self._draw(stdscr)
            key = stdscr.getch()
            if key == curses.KEY_RESIZE:
                continue

            n = len(self.tasks)
            if self.stage == "task":
                if key in (curses.KEY_RIGHT, ord("l"), ord(" "), ord("x")):
                    self.enabled[self.index] = not self.enabled[self.index]
                elif key in (curses.KEY_LEFT, ord("h")):
                    self.enabled[self.index] = not self.enabled[self.index]
                elif key in (curses.KEY_DOWN, ord("j"), curses.KEY_ENTER, 10, 13):
                    if self.index < n - 1:
                        self.index += 1
                    else:
                        self.stage = "review"
                elif key in (curses.KEY_UP, ord("k"), ord("b")):
                    if self.index > 0:
                        self.index -= 1
                elif key in (ord("a"),):
                    self.enabled = [True] * n
                elif key in (ord("n"),):
                    self.enabled = [False] * n
                elif key in (ord("q"), 27):
                    return []

            elif self.stage == "review":
                if key in (curses.KEY_ENTER, 10, 13):
                    return [t for t, e in zip(self.tasks, self.enabled) if e]
                elif key in (ord("b"), curses.KEY_LEFT, ord("h"), curses.KEY_UP, ord("k")):
                    self.stage = "task"
                    self.index = n - 1
                elif key in (ord("q"), 27):
                    return []

    # ---- 颜色 ----

    def _init_colors(self):
        import curses

        if not curses.has_colors():
            return
        try:
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_CYAN, -1)      # 标题/边框
            curses.init_pair(2, curses.COLOR_GREEN, -1)     # 启用/完成
            curses.init_pair(3, curses.COLOR_RED, -1)       # 跳过/错误
            curses.init_pair(4, curses.COLOR_YELLOW, -1)    # 状态说明
            curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_CYAN)  # 反白按钮
            self._colors = True
        except Exception:
            self._colors = False

    def _attr(self, color_pair: int) -> int:
        import curses

        return curses.color_pair(color_pair) if self._colors else curses.A_NORMAL

    # ---- 绘制 ----

    def _draw(self, stdscr):
        import curses

        stdscr.erase()
        h, w = stdscr.getmaxyx()
        if self.stage == "task":
            self._draw_task(stdscr, h, w)
        else:
            self._draw_review(stdscr, h, w)
        stdscr.refresh()

    def _draw_task(self, stdscr, h, w):
        import curses

        t = self.tasks[self.index]
        done, note = self.statuses[self.index]
        enabled = self.enabled[self.index]
        total = len(self.tasks)

        # 顶部标题
        title = " Ubuntu 新机初始化工具 "
        self._safe_add(stdscr, 0, max(0, (w - len(title)) // 2), title, self._attr(1) | curses.A_BOLD)
        stdscr.hline(1, 0, curses.ACS_HLINE, w)

        # 进度
        prog = f"第 {self.index + 1} / {total} 项"
        self._safe_add(stdscr, 2, 2, prog, self._attr(4))
        bar = self._progress(self.index + 1, total, w - 12)
        self._safe_add(stdscr, 3, 2, bar, self._attr(1))

        # 名称
        name = f"◆ {t.name}"
        self._safe_add(stdscr, 5, 4, name, self._attr(1) | curses.A_BOLD)

        # 描述
        self._safe_add(stdscr, 6, 4, t.description, curses.A_NORMAL)

        # 当前状态
        status_text = "已配置" if done else "未配置"
        status_attr = self._attr(2) if done else self._attr(4)
        self._safe_add(stdscr, 8, 4, f"当前状态：{status_text}", status_attr)
        if note and note != "未配置":
            self._safe_add(stdscr, 9, 4, f"　　{note}", self._attr(4))

        # 选项按钮
        by = max(11, h - 6)
        left = "启用"
        right = "跳过"
        self._draw_toggle(stdscr, by, 8, left, enabled)
        self._draw_toggle(stdscr, by, 8 + len(left) + 8, right, not enabled)

        # 底部分隔与按键提示
        stdscr.hline(h - 2, 0, curses.ACS_HLINE, w)
        hint = "←/→ 或 空格 切换   回车 下一步    b 上一步   a 全部启用   n 全部跳过   q 退出"
        self._safe_add(stdscr, h - 1, 2, hint, self._attr(4))

    def _draw_review(self, stdscr, h, w):
        import curses

        title = " 确认执行 "
        self._safe_add(stdscr, 0, max(0, (w - len(title)) // 2), title, self._attr(1) | curses.A_BOLD)
        stdscr.hline(1, 0, curses.ACS_HLINE, w)

        selected = [t for t, e in zip(self.tasks, self.enabled) if e]
        self._safe_add(stdscr, 2, 2, f"将执行 {len(selected)} 项，跳过 {len(self.tasks) - len(selected)} 项：",
                       self._attr(4))

        start = 3
        for i, t in enumerate(self.tasks):
            if start >= h - 3:
                break
            enabled = self.enabled[i]
            mark = "✓" if enabled else "·"
            mark_attr = self._attr(2) if enabled else self._attr(3)
            self._safe_add(stdscr, start, 4, mark, mark_attr | curses.A_BOLD)
            self._safe_add(stdscr, start, 6, t.name,
                           curses.A_NORMAL if enabled else self._attr(3))
            start += 1

        stdscr.hline(h - 2, 0, curses.ACS_HLINE, w)
        hint = "回车 开始执行    b 返回修改    q 退出"
        self._safe_add(stdscr, h - 1, 2, hint, self._attr(4))

    def _draw_toggle(self, stdscr, y, x, label, active):
        import curses

        text = f" {label} "
        attr = self._attr(5) | curses.A_BOLD if active else self._attr(3)
        self._safe_add(stdscr, y, x, text, attr)

    def _progress(self, cur, total, width) -> str:
        if width < 6:
            return ""
        filled = int(round((cur / total) * width))
        return "[" + "#" * filled + "-" * (width - filled) + "]"

    def _safe_add(self, win, y, x, text, attr=0):
        try:
            win.addnstr(y, x, text, win.getmaxyx()[1] - x - 1, attr)
        except curses.error:
            pass


# --------------------------------------------------------------------------
# 无 TTY 降级：逐项询问
# --------------------------------------------------------------------------

def _plain_select(tasks, cfg) -> list:
    print("Ubuntu 初始化工具（无 TTY 模式）——逐项确认，回车=推荐值")
    selected = []
    for t in tasks:
        done, note = _status_of(t, cfg)
        default = "n" if done else "y"
        label = "跳过（已配置）" if done else "启用"
        try:
            ans = input(f"[{label}] {t.name} — {t.description}  [Y/n] ").strip().lower()
        except EOFError:
            ans = ""
        want = (ans in ("", "y", "yes")) if default == "y" else (ans in ("y", "yes"))
        if want:
            selected.append(t)
    if not selected:
        return []
    print("将执行：")
    for t in selected:
        print(f"  - {t.name}")
    try:
        ans = input("确认开始？[y/N] ").strip().lower()
    except EOFError:
        ans = ""
    return selected if ans in ("y", "yes") else []
