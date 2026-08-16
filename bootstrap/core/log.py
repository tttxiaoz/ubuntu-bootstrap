"""日志：终端 + 文件 tee。"""

from __future__ import annotations

import datetime
import os
import sys

from ..ui.ansi import paint


class Logger:
    """同时写终端与日志文件；子进程输出经 stream() tee 落盘。"""

    def __init__(self, log_dir: str) -> None:
        os.makedirs(log_dir, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.path = os.path.join(log_dir, f"{stamp}.log")
        self._fh = open(self.path, "a", encoding="utf-8")

    def log(self, message: str = "", style: str | None = None) -> None:
        # 终端按 style 上色，日志文件始终写纯文本（不含 ANSI 码）
        if style and sys.stdout.isatty():
            print(paint(message, style), flush=True)
        else:
            print(message, flush=True)
        self._fh.write(message + "\n")
        self._fh.flush()

    def stream(self, line: str) -> None:
        """子进程输出：终端原样打印 + 文件落盘。"""
        print(line, flush=True)
        self._fh.write(line + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()
