"""pytest 共享夹具：路径注入、假日志/apt、Context 工厂。"""

from __future__ import annotations

import os
import sys

import pytest

# 让 pytest 能从仓库根目录导入 bootstrap 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bootstrap.config import Config  # noqa: E402
from bootstrap.core.task import Context  # noqa: E402


class FakeLog:
    """不落盘的日志替身，记录所有消息。"""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def log(self, msg: str = "", style: str | None = None) -> None:
        self.messages.append(msg)

    def stream(self, line: str) -> None:
        self.messages.append(line)


class FakeApt:
    """记录安装调用、不真实执行的 apt 替身。"""

    def __init__(self) -> None:
        self.installed: list[list[str]] = []

    def install(self, packages: list[str], **kw) -> None:
        self.installed.append(list(packages))


@pytest.fixture
def make_ctx():
    """Context 工厂：make_ctx(data) 用嵌套 dict 建 Config。"""

    def _make(data: dict | None = None, *, log=None, apt=None) -> Context:
        return Context(config=Config(data or {}), log=log or FakeLog(), apt=apt or FakeApt())

    return _make
