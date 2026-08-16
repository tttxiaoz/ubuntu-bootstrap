"""apt 源切换：支持 deb822（24.04+）与经典 sources.list（旧版兜底）两种格式。"""

from __future__ import annotations

import os

from ..config.schema import Param
from ..core.task import CheckResult, Context, Task, task
from ..platform import fs
from ..platform import sys as psys

_SOURCES_LIST = "/etc/apt/sources.list"
_SOURCES_DEB822 = "/etc/apt/sources.list.d/ubuntu.sources"

# 官方归档与安全服务器的 URI 前缀，切换镜像时一并改写（含 https 变体）
_OFFICIAL_HOSTS = (
    "http://archive.ubuntu.com/ubuntu",
    "https://archive.ubuntu.com/ubuntu",
    "http://security.ubuntu.com/ubuntu",
    "https://security.ubuntu.com/ubuntu",
)

# 「不更改」选项的显示名：选中时跳过换源，保持系统原有 apt 源
_SKIP_LABEL = "不更改"


def _rewrite_deb_uri(line: str, mirror: str) -> str:
    """把 deb 行的官方归档/安全服务器 URI 替换为镜像，保留其余字段。"""
    for host in _OFFICIAL_HOSTS:
        if host in line:
            return line.replace(host, mirror)
    return line


def _is_skip(config) -> bool:
    return config.get("apt.mirror") == _SKIP_LABEL


def _mirror_base(config) -> str:
    name = config.get("apt.mirror")
    mirrors = config.get("apt.mirrors") or {}
    if name in mirrors:
        return mirrors[name].rstrip("/")
    raise psys.TaskError("未配置 apt.mirrors/apt.mirror")


def _has_mirror(config) -> bool:
    """判断源文件是否已指向配置的镜像（检查生效的 deb / URIs 行）。"""
    mirror = _mirror_base(config)
    for path in (_SOURCES_LIST, _SOURCES_DEB822):
        for line in fs.read_lines(path):
            stripped = line.lstrip()
            if not stripped or stripped.startswith("#"):
                continue
            if (stripped.startswith("deb ") or stripped.startswith("URIs:")) and mirror in line:
                return True
    return False


def _is_deb822(codename: str) -> bool:
    # 22.04 及更早为经典 sources.list；24.04+ 为 deb822（正向判定，避免硬编码未来代号）
    return codename not in ("focal", "jammy")


@task(
    id="apt_mirror",
    name="切换 apt 源为国内镜像",
    description="将 apt 源切换为配置的国内镜像（默认清华 TUNA）",
    params=[Param("apt.mirror", "choice", default="清华 TUNA",
                  choices="config:apt.mirrors", label="apt 镜像源")],
)
class AptMirrorTask(Task):
    def check(self, ctx: Context) -> CheckResult:
        if _is_skip(ctx.config):
            return CheckResult(True, "已选择不更改源")
        if _has_mirror(ctx.config):
            return CheckResult(True, "已指向镜像源")
        return CheckResult(False, "未切换镜像源")

    def run(self, ctx: Context) -> None:
        if _is_skip(ctx.config):
            ctx.log.log("⏭ 已选择不更改 apt 源，跳过。")
            return
        codename = psys.detect_codename()
        mirror = _mirror_base(ctx.config)
        if _is_deb822(codename):
            self._patch_deb822(codename, mirror)
        else:
            self._patch_classic(codename, mirror)

    def _patch_classic(self, codename: str, mirror: str) -> None:
        """经典格式：改写 sources.list 中 deb 行的归档/安全服务器地址。"""
        lines = fs.read_lines(_SOURCES_LIST)
        if not lines:
            lines = [
                f"deb {mirror} {codename} main restricted universe multiverse",
                f"deb {mirror} {codename}-updates main restricted universe multiverse",
                f"deb {mirror} {codename}-backports main restricted universe multiverse",
                f"deb {mirror} {codename}-security main restricted universe multiverse",
            ]
        out = []
        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith("deb ") and "ubuntu.com" in line:
                out.append(_rewrite_deb_uri(line, mirror))
            else:
                out.append(line)
        fs.backup_write(_SOURCES_LIST, "\n".join(out) + "\n")

    def _patch_deb822(self, codename: str, mirror: str) -> None:
        """deb822 格式：改写 URIs: 字段（Suites: 保留原样，codename 不随镜像改变）。"""
        path = _SOURCES_DEB822
        if not os.path.exists(path):
            fs.backup_write(path, _default_deb822(codename, mirror))
            return
        lines = fs.read_lines(path)
        out = []
        for line in lines:
            if line.startswith("URIs:"):
                out.append(f"URIs: {mirror}")
            else:
                out.append(line)
        fs.backup_write(path, "\n".join(out) + "\n")


def _default_deb822(codename: str, mirror: str) -> str:
    return (
        "Types: deb\n"
        f"URIs: {mirror}\n"
        f"Suites: {codename} {codename}-updates {codename}-backports\n"
        "Components: main restricted universe multiverse\n"
        "Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n"
        "\n"
        "Types: deb\n"
        f"URIs: {mirror}\n"
        f"Suites: {codename}-security\n"
        "Components: main restricted universe multiverse\n"
        "Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n"
    )
