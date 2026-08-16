"""终端 UI：rich（彩色展示）+ questionary（交互选择），失败逐级降级到 ANSI 纯文本。

依赖探测采用 lazy import；首次运行若缺失会通过 pip 自动安装
（Ubuntu 24.04 的 PEP 668 限制用 --break-system-packages 兜底）。
任何一步失败都降级为 ANSI 彩色纯文本 / 数字选择，不影响初始化功能。
"""

from __future__ import annotations

import sys

from . import utils

# --------------------------------------------------------------------------
# 依赖探测（lazy import，避免顶层强依赖 rich/questionary）
# --------------------------------------------------------------------------

_rich_state: bool | None = None
_questionary_state: bool | None = None


def rich_available() -> bool:
    global _rich_state
    if _rich_state is None:
        try:
            import rich  # noqa: F401
            _rich_state = True
        except ImportError:
            _rich_state = False
    return _rich_state


def questionary_available() -> bool:
    global _questionary_state
    if _questionary_state is None:
        try:
            import questionary  # noqa: F401
            _questionary_state = True
        except ImportError:
            _questionary_state = False
    return _questionary_state


def _reset_detection() -> None:
    global _rich_state, _questionary_state
    _rich_state = None
    _questionary_state = None


# --------------------------------------------------------------------------
# 依赖安装
# --------------------------------------------------------------------------

def _packages(cfg) -> list:
    return list(getattr(cfg, "TUI_PACKAGES", None) or ["rich", "questionary"])


def _index_url(cfg) -> str:
    return getattr(cfg, "PIP_INDEX_URL", "") or ""


def _pip_install(cfg, log=None) -> bool:
    """用 pip 安装 UI 依赖；返回是否整条命令成功。"""
    base = [sys.executable, "-m", "pip", "install", "--quiet",
            "--disable-pip-version-check"]
    index = _index_url(cfg)
    if index:
        base += ["-i", index]
    pkgs = _packages(cfg)

    first = utils.run_cmd(base + pkgs, check=False, capture=True)
    if first.returncode == 0:
        return True
    # Ubuntu 24.04（PEP 668）会报 externally-managed，加 --break-system-packages 重试
    err = (first.stderr or "") + (first.stdout or "")
    if "externally-managed" in err or "break-system-packages" in err:
        retry = utils.run_cmd(base + ["--break-system-packages"] + pkgs,
                              check=False, capture=True)
        return retry.returncode == 0
    return False


def ensure_deps(cfg, log=None) -> tuple[bool, bool]:
    """确保 rich/questionary 可用，缺失时尝试 pip 安装。返回 (rich_ok, questionary_ok)。"""
    if rich_available() and questionary_available():
        return True, True
    msg = "未检测到交互 UI 依赖（rich/questionary），正在通过 pip 安装（网络不通约 1 分钟后自动跳过）..."
    if log:
        log(msg)
    else:
        print(msg, flush=True)
    _pip_install(cfg, log)
    _reset_detection()
    return rich_available(), questionary_available()


# --------------------------------------------------------------------------
# ANSI 颜色（rich 与纯文本降级共用）
# --------------------------------------------------------------------------

_C = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "gray": "\033[90m",
}


def _paint(text: str, *styles: str) -> str:
    codes = "".join(_C[s] for s in styles if s in _C)
    return f"{codes}{text}{_C['reset']}" if codes else text


# --------------------------------------------------------------------------
# 展示原语
# --------------------------------------------------------------------------

def banner(title: str) -> None:
    if rich_available():
        from rich.console import Console
        from rich.panel import Panel
        Console().print(Panel(title, style="cyan bold", expand=False))
    else:
        print()
        print(_paint(f"  {title}  ", "cyan", "bold"))
        print()


def task_header(index: int, total: int, name: str, description: str,
                status_tag: str, note: str = "") -> None:
    if rich_available():
        from rich.console import Console
        c = Console()
        c.print(f"[bold magenta][{index}/{total}][/bold magenta] [bold]{name}[/bold]")
        color = "green" if status_tag == "已配置" else "yellow"
        c.print(f"  [dim]{description}[/dim]   （当前状态：[{color}]{status_tag}[/{color}]）")
        if note:
            c.print(f"  [dim]{note}[/dim]")
    else:
        print()
        print(_paint(f"[{index}/{total}] {name}", "bold", "magenta"))
        print(_paint(f"  {description}   （当前状态：{status_tag}）", "dim"))
        if note:
            print(_paint(f"  {note}", "dim"))


def heading(text: str) -> None:
    if rich_available():
        from rich.console import Console
        Console().print(f"[bold blue]{text}[/bold blue]")
    else:
        print(_paint(text, "blue", "bold"))


def status_line(mark: str, name: str, kind: str) -> None:
    """kind: ok | skip | fail | ?"""
    color = {"ok": "green", "skip": "yellow", "fail": "red"}.get(kind, "gray")
    if rich_available():
        from rich.console import Console
        Console().print(f"[{color} bold]{mark} {name}[/{color} bold]")
    else:
        print(_paint(f"{mark} {name}", color, "bold"))


# --------------------------------------------------------------------------
# 交互原语
# --------------------------------------------------------------------------

def choose(options: list, *, header: str = "", selected: str = "") -> str | None:
    """单选，返回选中项；取消返回 None。questionary 缺失时降级为数字选择。"""
    if not options:
        return None
    if questionary_available():
        import questionary
        default = selected if selected in options else None
        return questionary.select(header or "请选择", choices=list(options),
                                  default=default).ask()
    # 降级：数字选择（回车=当前值）
    if header:
        print(_paint(header, "cyan"))
    for i, o in enumerate(options):
        mark = ">" if o == selected else " "
        print(f"  {_paint(mark, 'green')} {i + 1}. {o}")
    hint = f"请选择 [1-{len(options)}]" + (f"（回车={selected}）" if selected else "")
    try:
        raw = input(f"{hint}: ").strip()
    except EOFError:
        return None
    if raw.isdigit() and 1 <= int(raw) <= len(options):
        return options[int(raw) - 1]
    if not raw and selected in options:
        return selected
    return None


def confirm(prompt: str, *, default: bool = True) -> bool:
    """确认框，返回布尔；default 决定回车默认值。questionary 缺失时降级 input。"""
    if questionary_available():
        import questionary
        result = questionary.confirm(prompt, default=default).ask()
        return bool(result) if result is not None else default
    hint = "[Y/n]" if default else "[y/N]"
    try:
        raw = input(f"{prompt} {hint} ").strip().lower()
    except EOFError:
        return default
    if not raw:
        return default
    return raw in ("y", "yes")


def multiselect(options: list, *, header: str = "", selected: list | None = None) -> list:
    """多选，返回选中的列表；questionary 缺失时降级为逗号分隔数字选择。"""
    if not options:
        return []
    preselect = list(selected) if selected else list(options)
    if questionary_available():
        import questionary
        # checkbox 的 default 只接受单个值，预设多项需用 Choice(..., checked=True)
        choices = [questionary.Choice(o, checked=(o in preselect)) for o in options]
        result = questionary.checkbox(header or "请选择", choices=choices).ask()
        return list(result) if result else preselect
    # 降级：数字多选（回车=默认全选/已选）
    if header:
        print(_paint(header or "请选择（回车=默认）", "cyan"))
    for i, o in enumerate(options):
        mark = "x" if o in preselect else " "
        print(f"  {_paint(mark, 'green')} {i + 1}. {o}")
    try:
        raw = input("输入序号（逗号分隔，回车=默认）: ").strip()
    except EOFError:
        return preselect
    if not raw:
        return preselect
    idxs = [int(x) for x in raw.replace(",", " ").split() if x.isdigit()]
    return [options[i - 1] for i in idxs if 1 <= i <= len(options)]


def password(prompt: str) -> str | None:
    """输入密码（两次确认），返回密码或 None（取消/不一致）。"""
    if questionary_available():
        import questionary
        p1 = questionary.password(f"{prompt}（输入新密码）:").ask()
        if not p1:
            return None
        p2 = questionary.password(f"{prompt}（再次确认）:").ask()
        if p1 != p2:
            print(_paint("两次输入不一致，已跳过", "red"))
            return None
        return p1
    # 降级：getpass
    import getpass
    try:
        p1 = getpass.getpass(f"{prompt}: ")
    except EOFError:
        return None
    if not p1:
        return None
    try:
        p2 = getpass.getpass(f"再次确认 {prompt}: ")
    except EOFError:
        return None
    if p1 != p2:
        print(_paint("两次输入不一致，已跳过", "red"))
        return None
    return p1


# --------------------------------------------------------------------------
# 结果摘要
# --------------------------------------------------------------------------

def print_summary_table(rows: list) -> None:
    """rows: [(name, mark)]，mark 为 ✅/⏭/❌。rich 可用时渲染表格，否则 ANSI 纯文本。"""
    if rich_available():
        from rich.console import Console
        from rich.table import Table
        table = Table(title="执行结果", title_justify="left")
        table.add_column("任务", style="bold")
        table.add_column("状态")
        for name, mark in rows:
            style = {"✅": "green", "⏭": "yellow", "❌": "red"}.get(mark, "white")
            table.add_row(name, f"[{style}]{mark}[/{style}]")
        Console().print(table)
    else:
        print("\n========== 执行结果 ==========")
        for name, mark in rows:
            color = {"✅": "green", "⏭": "yellow", "❌": "red"}.get(mark, "gray")
            print(_paint(f"{mark} {name}", color, "bold"))
