"""通用工具函数：命令执行、codename 检测、apt 封装、备份写入、真实用户识别。"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys


class TaskError(RuntimeError):
    """任务执行失败时抛出。"""


def run_cmd(
    cmd: list[str],
    *,
    check: bool = True,
    capture: bool = False,
    env: dict | None = None,
    input_text: str | None = None,
    log: "callable | None" = None,
) -> subprocess.CompletedProcess:
    """执行命令，stdout/stderr 透传到终端（或按 capture 捕获）。

    check=True 时非零退出码抛 TaskError；日志回调 log 用于写入日志文件。
    """
    if log is not None:
        log("$ " + " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=capture,
            text=True,
            env=env,
            input=input_text,
        )
    except FileNotFoundError as exc:
        raise TaskError(f"命令不存在: {cmd[0]}") from exc

    if check and result.returncode != 0:
        detail = ""
        if capture:
            detail = (result.stderr or result.stdout or "").strip()
            if detail:
                detail = f": {detail}"
        raise TaskError(f"命令失败 (退出码 {result.returncode}): {' '.join(cmd)}{detail}")
    return result


def command_exists(name: str) -> bool:
    """检查命令是否在 PATH 中。"""
    return shutil.which(name) is not None


def package_installed(name: str) -> bool:
    """用 dpkg -s 判断包是否已安装（静默）。"""
    result = run_cmd(["dpkg", "-s", name], check=False, capture=True)
    return result.returncode == 0


def detect_codename() -> str:
    """从 /etc/os-release 读取版本代号，如 jammy / noble / resolute。"""
    for line in _read_lines("/etc/os-release"):
        if line.startswith("VERSION_CODENAME="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise TaskError("无法检测系统版本代号（VERSION_CODENAME）")


def detect_arch() -> str:
    """返回第三方二进制发布（如 neovim tarball）用的架构名：x86_64 | arm64。"""
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "x86_64"
    if machine in ("aarch64", "arm64"):
        return "arm64"
    return machine


def real_user() -> str:
    """识别真实登录用户（通过 sudo 运行时为 SUDO_USER），无则回退 root。"""
    return os.environ.get("SUDO_USER") or os.environ.get("USER") or "root"


def real_home() -> str:
    """真实用户的家目录（优先用 pwd 数据库，回退 HOME）。"""
    user = real_user()
    try:
        import pwd

        return pwd.getpwnam(user).pw_dir
    except (ImportError, KeyError):
        if user == "root":
            return "/root"
        return os.path.expanduser(f"~{user}")


def _read_lines(path: str) -> list[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read().splitlines()
    except OSError:
        return []


def read_lines(path: str) -> list[str]:
    """读取文件行（不存在/不可读返回空列表）。"""
    return _read_lines(path)


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
    lines = _read_lines(path)
    regex = re.compile(pattern)
    matched = False
    out = []
    for line in lines:
        if regex.search(line):
            if not matched:
                out.append(replacement)
                matched = True
            # 已写入一次，后续重复匹配行丢弃
        else:
            out.append(line)
    if not matched:
        out.append(fallback)
    backup_write(path, "\n".join(out) + "\n")


# apt-get update 的一次性标志（模块级，进程内只 update 一次）
_APT_UPDATED = False


def apt_install(packages: list[str], log: "callable | None" = None) -> None:
    """安装包；全程仅做一次 apt-get update（供多个安装类任务复用）。"""
    global _APT_UPDATED
    if not _APT_UPDATED:
        run_cmd(["apt-get", "update"], log=log)
        _APT_UPDATED = True
    run_cmd(["apt-get", "install", "-y", "--fix-missing"] + packages, log=log)
