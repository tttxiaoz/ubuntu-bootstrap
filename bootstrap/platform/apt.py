"""apt 封装：进程内一次 update 的安装管理。"""

from __future__ import annotations

from collections.abc import Callable

from .sys import run_cmd


class AptManager:
    """管理 apt-get update 的一次性执行（单次运行内共享同一实例，消除模块级全局）。"""

    def __init__(self) -> None:
        self._updated = False

    def install(self, packages: list[str], *, log: Callable[..., None] | None = None,
                tee: Callable[[str], None] | None = None) -> None:
        if not packages:
            return
        if not self._updated:
            run_cmd(["apt-get", "update"], log=log, tee=tee)
            self._updated = True
        run_cmd(["apt-get", "install", "-y", "--fix-missing"] + packages, log=log, tee=tee)
