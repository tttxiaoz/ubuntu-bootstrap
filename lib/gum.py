"""gum（Charmbracelet）探测、引导安装与组件封装。

gum 是单一静态二进制，提供漂亮的 TUI 组件。不在 Ubuntu 默认 apt 源，
首次运行若缺失会从 GitHub release 下载。所有组件封装都返回字符串/布尔，
供 lib/ui.py 的 _gum_run 使用。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile

from . import utils

GUM_INSTALL_PATH = "/usr/local/bin/gum"
_DEFAULT_API = "https://api.github.com/repos/charmbracelet/gum/releases/latest"
_DEFAULT_BASE = "https://github.com/charmbracelet/gum/releases/download"


def _download_base(cfg) -> str:
    return getattr(cfg, "GUM_DOWNLOAD_BASE", None) or _DEFAULT_BASE


def _api(cfg) -> str:
    return getattr(cfg, "GUM_API", None) or _DEFAULT_API


def gum_available() -> bool:
    """gum 是否已在 PATH 中。"""
    return shutil.which("gum") is not None


def ensure_gum(cfg=None, log=None) -> bool:
    """确保 gum 可用；缺失时尝试从 GitHub 下载安装。返回是否成功。"""
    if gum_available():
        return True
    if log:
        log("未找到 gum，尝试下载安装...")
    try:
        version = _latest_version(cfg, log)
        arch = utils.detect_arch()
        # 版本 tag 形如 v0.14.5，资产名形如 gum_0.14.5_Linux_x86_64.tar.gz
        bare = version.lstrip("v")
        asset = f"gum_{bare}_Linux_{arch}.tar.gz"
        url = f"{_download_base(cfg)}/{version}/{asset}"
        with tempfile.TemporaryDirectory() as tmp:
            tarball = os.path.join(tmp, asset)
            utils.run_cmd(["curl", "-fsSL", "-o", tarball, url], log=log)
            utils.run_cmd(["tar", "-xzf", tarball, "-C", tmp], log=log)
            src = os.path.join(tmp, "gum")
            if not os.path.exists(src):
                raise utils.TaskError("解压后未找到 gum 二进制")
            utils.run_cmd(["install", "-m", "0755", src, GUM_INSTALL_PATH], log=log)
        return gum_available()
    except Exception as exc:
        if log:
            log(f"gum 安装失败：{exc}")
        return False


def _latest_version(cfg, log=None) -> str:
    """查询 gum 最新 release tag（如 v0.14.5）。"""
    raw = utils.run_cmd(["curl", "-fsSL", _api(cfg)], capture=True).stdout
    data = json.loads(raw)
    return data["tag_name"]


def _run_gum(args: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess:
    """调用 gum 子进程；gum 缺失时返回失败进程（不抛异常）。"""
    if not gum_available():
        return subprocess.CompletedProcess(["gum", *args], 1, "", "gum 未安装")
    return utils.run_cmd(["gum", *args], check=False, capture=True,
                         input_text=input_text)


def choose(options: list[str], *, header: str = "", selected: str = "",
           limit: int = 1) -> str | None:
    """单选（默认），返回选中项；取消返回 None。"""
    if not options:
        return None
    args = ["choose"]
    if header:
        args += ["--header", header]
    if selected:
        args += ["--selected", selected]
    if limit:
        args += ["--limit", str(limit)]
    result = _run_gum(args, input_text="\n".join(options) + "\n")
    out = (result.stdout or "").strip()
    return out if result.returncode == 0 and out else None


def confirm(prompt: str, *, default: bool = True) -> bool:
    """确认框，返回布尔；默认 default。"""
    args = ["confirm", prompt]
    if default:
        args += ["--default"]
    result = _run_gum(args)
    return result.returncode == 0


def style(text: str, *, foreground: str | None = None, background: str | None = None,
          bold: bool = False, padding: str | None = None, border: str | None = None,
          border_foreground: str | None = None) -> None:
    """用 gum style 打印一段文本（无返回值）。gum 缺失时退化为 print。"""
    if not gum_available():
        print(text)
        return
    args = ["style"]
    if foreground:
        args += ["--foreground", foreground]
    if background:
        args += ["--background", background]
    if bold:
        args += ["--bold"]
    if padding:
        args += ["--padding", padding]
    if border:
        args += ["--border", border]
    if border_foreground:
        args += ["--border-foreground", border_foreground]
    utils.run_cmd(["gum", *args], check=False, input_text=text)


def spin(title: str, cmd: list[str]) -> None:
    """用 spinner 包裹一个命令执行（用于快速探测，不用于需要流式输出的命令）。"""
    if not gum_available():
        utils.run_cmd(cmd, check=False)
        return
    utils.run_cmd(["gum", "spin", "--title", title, "--"] + cmd, check=False)
