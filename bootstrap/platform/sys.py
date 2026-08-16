"""命令执行与系统探测。"""

from __future__ import annotations

import platform
import shutil
import subprocess
from collections.abc import Callable

from .fs import read_lines


class TaskError(RuntimeError):
    """任务执行失败时抛出。"""


def run_cmd(
    cmd: list[str],
    *,
    check: bool = True,
    capture: bool = False,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
    tee: Callable[[str], None] | None = None,
    log: Callable[..., None] | None = None,
) -> subprocess.CompletedProcess:
    """执行命令。

    check=True 时非零退出码抛 TaskError；log 记录命令行本身；
    tee 把子进程输出逐行回调（用于同时写日志文件）。
    """
    if log is not None:
        log("$ " + " ".join(cmd))
    try:
        if capture:
            result = subprocess.run(cmd, check=False, capture_output=True,
                                    text=True, env=env, input=input_text)
        elif tee is not None:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, env=env,
                                    stdin=subprocess.PIPE if input_text is not None else None)
            if input_text is not None:
                out, _ = proc.communicate(input_text)
                for line in (out or "").splitlines():
                    tee(line)
            else:
                assert proc.stdout is not None
                for line in proc.stdout:
                    tee(line.rstrip("\n"))
                proc.wait()
            result = subprocess.CompletedProcess(cmd, proc.returncode, "", "")
        else:
            result = subprocess.run(cmd, check=False, text=True, env=env,
                                    input=input_text)
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
    """从 /etc/os-release 读取版本代号，如 noble / resolute。"""
    for line in read_lines("/etc/os-release"):
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
