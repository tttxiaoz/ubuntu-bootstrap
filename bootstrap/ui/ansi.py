"""ANSI 颜色与着色原语（无依赖叶子模块，供日志与终端共用）。"""

from __future__ import annotations

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


def paint(text: str, *styles: str) -> str:
    """ANSI 着色。"""
    return _paint(text, *styles)
