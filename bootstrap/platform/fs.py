"""文件操作：读取、备份写入、按行替换。"""

from __future__ import annotations

import os
import re
import shutil


def read_lines(path: str) -> list[str]:
    """读取文件行（不存在/不可读返回空列表）。"""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read().splitlines()
    except OSError:
        return []


def backup_write(path: str, content: str) -> None:
    """先备份（若尚未备份）再写入文件。"""
    if os.path.exists(path) and not os.path.exists(path + ".bak"):
        shutil.copy2(path, path + ".bak")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def backup_file(path: str) -> None:
    """仅备份（若尚未备份）。"""
    if os.path.exists(path) and not os.path.exists(path + ".bak"):
        shutil.copy2(path, path + ".bak")


def replace_or_append(path: str, pattern: str, replacement: str, fallback: str) -> None:
    """按行正则替换；若整文件无匹配则在文件末尾追加 fallback 行。

    若有多行匹配，首处写入 replacement、其余重复行丢弃，避免残留旧值。
    """
    lines = read_lines(path)
    regex = re.compile(pattern)
    matched = False
    out = []
    for line in lines:
        if regex.search(line):
            if not matched:
                out.append(replacement)
                matched = True
        else:
            out.append(line)
    if not matched:
        out.append(fallback)
    backup_write(path, "\n".join(out) + "\n")
