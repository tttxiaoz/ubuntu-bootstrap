"""交互式逐步执行向导。

流程：逐个任务展示卡片 → 选择执行/跳过 →（可选）选择该任务的配置项 → 立即执行 → 下一项。
执行时临时退出 curses，把命令输出流式打印到终端，完成后再回到界面。

无 TTY 时降级为纯文本逐项询问。
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
    """逐步执行向导，返回 {task.id: status}。"""
    if sys.stdout.isatty() and sys.stdin.isatty():
        try:
            return _wizard_run(tasks, cfg, force, log_dir)
        except Exception:
            # curses 失败降级
            pass
    return _plain_run(tasks, cfg, force, log_dir)


# --------------------------------------------------------------------------
# curses 向导
# --------------------------------------------------------------------------

def _wizard_run(tasks, cfg, force, log_dir) -> dict:
    import curses

    from . import runner

    logger = runner.Logger(log_dir)
    wizard = _Wizard(tasks, cfg, logger, force)
    try:
        results = curses.wrapper(wizard.run)
    finally:
        logger.close()
    runner.print_summary(results)
    return results


class _Wizard:
    def __init__(self, tasks, cfg, logger, force):
        from . import runner

        self.tasks = runner.topo_sort(tasks)
        self.cfg = cfg
        self.logger = logger
        self.force = force
        self.stdscr = None
        self.results: dict = {}
        self.task_index = 0

        # 预计算各任务状态（用于显示与默认选择）
        self.statuses = [_status_of(t, cfg) for t in self.tasks]

        # 当前任务交互状态
        self.enabled = False
        self.qs = []
        self.q_meta = []
        self.qidx = 0
        self.qs_active = False

        self._colors = False

    # ---- 主流程 ----

    def run(self, stdscr) -> dict:
        import curses

        self.stdscr = stdscr
        curses.curs_set(0)
        self._init_colors()

        while self.task_index < len(self.tasks):
            task = self.tasks[self.task_index]
            done, _note = self.statuses[self.task_index]
            self.enabled = not done  # 默认：未配置的执行，已配置的跳过
            self.qs = questions_for_task(self.cfg, task.id)
            self._build_q_meta()
            self.qidx = 0
            self.qs_active = False

            action = self._interact()
            if action == "quit":
                break
            if action == "skip":
                self.results[task.id] = "skip"
                self.task_index += 1
                continue

            # 执行：临时退出 curses，流式输出
            self._suspend()
            from . import runner

            status = runner.run_one(task, self.cfg, self.logger, force=self.force)
            self.results[task.id] = status
            print()
            try:
                input("按回车继续...")
            except EOFError:
                pass
            self._resume()
            self.task_index += 1

        return self.results

    # ---- 交互循环 ----

    def _interact(self) -> str:
        """任务卡片 + 配置项子界面的 curses 循环，返回 "run" | "skip" | "quit"。"""
        import curses

        while True:
            self._draw()
            key = self.stdscr.getch()
            if key == curses.KEY_RESIZE:
                continue

            if self.qs_active and self.qs:
                r = self._handle_question_key(key)
                if r == "run":
                    self._apply_answers()
                    return "run"
                if r == "back":
                    self.qs_active = False
                    continue
                if r == "quit":
                    return "quit"
                continue

            # 任务卡片阶段
            if key in (curses.KEY_RIGHT, curses.KEY_LEFT, ord(" "), ord("x")):
                self.enabled = not self.enabled
            elif key in (curses.KEY_ENTER, 10, 13):
                if not self.enabled:
                    return "skip"
                if self.qs:
                    self.qs_active = True
                    self.qidx = 0
                else:
                    return "run"
            elif key in (ord("q"), 27):
                return "quit"
        return "quit"

    def _handle_question_key(self, key) -> str | None:
        import curses

        meta = self.q_meta[self.qidx]
        q = meta["q"]
        if q["type"] == "choice":
            if key in (curses.KEY_DOWN, ord("j")):
                meta["cursor"] = (meta["cursor"] + 1) % len(meta["options"])
            elif key in (curses.KEY_UP, ord("k")):
                meta["cursor"] = (meta["cursor"] - 1) % len(meta["options"])
            elif key in (curses.KEY_ENTER, 10, 13):
                return self._advance_question()
            elif key in (ord("b"), 27):
                return "back"
            elif key in (ord("q"),):
                return "quit"
        else:  # bool
            if key in (curses.KEY_RIGHT, curses.KEY_LEFT, ord(" "), ord("x")):
                meta["bool_val"] = not meta["bool_val"]
            elif key in (curses.KEY_ENTER, 10, 13):
                return self._advance_question()
            elif key in (ord("b"), 27):
                return "back"
            elif key in (ord("q"),):
                return "quit"
        return None

    def _advance_question(self) -> str | None:
        if self.qidx < len(self.q_meta) - 1:
            self.qidx += 1
            return None
        return "run"

    # ---- 配置项 ----

    def _build_q_meta(self):
        self.q_meta = []
        for q in self.qs:
            opts = resolve_options(self.cfg, q)
            meta = {"q": q, "options": opts}
            if q["type"] == "choice":
                cur = getattr(self.cfg, q["config_key"], None)
                meta["cursor"] = opts.index(cur) if cur in opts else 0
            else:
                meta["bool_val"] = getattr(self.cfg, q["config_key"], "yes") == "yes"
            self.q_meta.append(meta)

    def _apply_answers(self):
        for meta in self.q_meta:
            q = meta["q"]
            if q["type"] == "bool":
                setattr(self.cfg, q["config_key"], "yes" if meta["bool_val"] else "no")
            else:
                setattr(self.cfg, q["config_key"], meta["options"][meta["cursor"]])

    # ---- curses 生命周期 ----

    def _suspend(self):
        import curses

        curses.endwin()

    def _resume(self):
        import curses

        self.stdscr = curses.initscr()
        curses.cbreak()
        curses.noecho()
        self.stdscr.keypad(True)
        curses.curs_set(0)
        self._init_colors()

    def _init_colors(self):
        import curses

        if not self._colors and curses.has_colors():
            try:
                curses.start_color()
                curses.use_default_colors()
                curses.init_pair(1, curses.COLOR_CYAN, -1)       # 标题
                curses.init_pair(2, curses.COLOR_GREEN, -1)      # 成功/已配置
                curses.init_pair(3, curses.COLOR_RED, -1)        # 失败
                curses.init_pair(4, curses.COLOR_YELLOW, -1)     # 提示/未配置
                curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_CYAN)  # 反白按钮/选中
                self._colors = True
            except Exception:
                self._colors = False

    def _attr(self, pair: int, extra=0) -> int:
        import curses

        base = curses.color_pair(pair) if self._colors else curses.A_NORMAL
        return base | extra

    # ---- 绘制 ----

    def _draw(self):
        import curses

        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        self._draw_header(h, w)
        # 卡片区域
        y0, x0 = 4, 2
        hh = h - 6
        ww = w - 4
        if hh < 6 or ww < 20:
            self._safe_add(2, 2, "窗口太小", 0)
            return
        self._box(y0, x0, hh, ww)
        if self.qs_active and self.qs:
            self._draw_questions(y0, x0, hh, ww)
        else:
            self._draw_task_card(y0, x0, hh, ww)
        self._draw_footer(h, w)
        self.stdscr.refresh()

    def _draw_header(self, h, w):
        import curses

        title = " Ubuntu 新机初始化工具 "
        self._safe_add(0, max(0, (w - len(title)) // 2), title,
                       self._attr(5, curses.A_BOLD))
        # 进度
        total = len(self.tasks)
        prog = f" 第 {self.task_index + 1} / {total} 项 "
        self._safe_add(2, 2, prog, self._attr(4))
        bar_w = max(10, w - 20)
        self._safe_add(2, 12, self._progress(self.task_index + 1, total, bar_w), self._attr(1))

    def _draw_task_card(self, y0, x0, hh, ww):
        import curses

        task = self.tasks[self.task_index]
        done, note = self.statuses[self.task_index]
        cx = x0 + 2
        inner_w = ww - 4

        # 任务名
        self._safe_add(y0 + 1, cx, f"◆ {task.name}", self._attr(1, curses.A_BOLD))
        # 描述
        self._safe_add(y0 + 2, cx, task.description[:inner_w], curses.A_NORMAL)

        # 状态胶囊
        status_text = "已配置" if done else "未配置"
        color = 2 if done else 4
        self._safe_add(y0 + 4, cx, "当前状态：", curses.A_NORMAL)
        self._safe_add(y0 + 4, cx + 6, f" {status_text} ",
                       self._attr(5, curses.A_BOLD) if done else self._attr(4, curses.A_BOLD))
        if note:
            self._safe_add(y0 + 5, cx, f"  {note[:inner_w]}", self._attr(4))

        # 执行/跳过切换
        by = y0 + hh - 3
        self._draw_toggle(by, cx, " 执行 ", self.enabled)
        self._draw_toggle(by, cx + 8, " 跳过 ", not self.enabled)

        if self.qs:
            self._safe_add(by + 1, cx, "（执行前将询问该任务的配置项）", self._attr(4))

    def _draw_questions(self, y0, x0, hh, ww):
        import curses

        task = self.tasks[self.task_index]
        cx = x0 + 2
        inner_w = ww - 4

        self._safe_add(y0 + 1, cx, f"◆ {task.name} — 配置项",
                       self._attr(1, curses.A_BOLD))
        self._safe_add(y0 + 2, cx, f"（{self.qidx + 1}/{len(self.q_meta)}）", self._attr(4))

        meta = self.q_meta[self.qidx]
        q = meta["q"]
        self._safe_add(y0 + 4, cx, q["name"], self._attr(5, curses.A_BOLD))

        if q["type"] == "choice":
            for i, opt in enumerate(meta["options"]):
                if y0 + 6 + i >= y0 + hh - 3:
                    break
                mark = "▶" if i == meta["cursor"] else "  "
                attr = self._attr(5, curses.A_BOLD) if i == meta["cursor"] else curses.A_NORMAL
                self._safe_add(y0 + 6 + i, cx + 2, f"{mark} {opt}", attr)
        else:
            yes = " ● 是 " if meta["bool_val"] else " ○ 是 "
            no = " ● 否 " if not meta["bool_val"] else " ○ 否 "
            self._draw_toggle(y0 + 6, cx + 2, yes, meta["bool_val"])
            self._draw_toggle(y0 + 6, cx + 12, no, not meta["bool_val"])

    def _draw_footer(self, h, w):
        import curses

        self._safe_add(h - 1, 0, " " * w, self._attr(5))
        if self.qs_active and self.qs:
            q = self.q_meta[self.qidx]["q"]
            if q["type"] == "choice":
                hint = " ↑/↓ 选择   回车 确认   b 返回   q 退出 "
            else:
                hint = " ←/→ 或 空格 切换   回车 确认   b 返回   q 退出 "
        else:
            hint = " ←/→ 或 空格 切换执行/跳过   回车 确认   q 退出 "
        self._safe_add(h - 1, 2, hint, self._attr(5, curses.A_BOLD))

    # ---- 小工具 ----

    def _draw_toggle(self, y, x, label, active):
        import curses

        attr = self._attr(5, curses.A_BOLD) if active else self._attr(3)
        self._safe_add(y, x, label, attr)

    def _progress(self, cur, total, width) -> str:
        if width < 6 or total == 0:
            return ""
        filled = int(round(cur / total * width))
        return "[" + "#" * filled + "-" * (width - filled) + "]"

    def _box(self, y, x, hh, ww):
        import curses

        s = self.stdscr
        for i in range(ww):
            try:
                s.addch(y, x + i, curses.ACS_HLINE)
                s.addch(y + hh - 1, x + i, curses.ACS_HLINE)
            except curses.error:
                pass
        for j in range(hh):
            try:
                s.addch(y + j, x, curses.ACS_VLINE)
                s.addch(y + j, x + ww - 1, curses.ACS_VLINE)
            except curses.error:
                pass
        for ch, yy, xx in ((curses.ACS_ULCORNER, y, x),
                           (curses.ACS_URCORNER, y, x + ww - 1),
                           (curses.ACS_LLCORNER, y + hh - 1, x),
                           (curses.ACS_LRCORNER, y + hh - 1, x + ww - 1)):
            try:
                s.addch(yy, xx, ch)
            except curses.error:
                pass

    def _safe_add(self, y, x, text, attr=0):
        import curses

        try:
            self.stdscr.addnstr(y, x, text, self.stdscr.getmaxyx()[1] - x - 1, attr)
        except curses.error:
            pass


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
        try:
            ans = input(f"[{label}] {t.name} — {t.description}  [Y/n] ").strip().lower()
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
