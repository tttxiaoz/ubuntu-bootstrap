"""apt 源切换：支持 22.04（sources.list）与 24.04/26.04（deb822 .sources）两种格式。"""

from __future__ import annotations

import os

from .base import Task
from .. import utils

_SOURCES_LIST = "/etc/apt/sources.list"
_SOURCES_DEB822 = "/etc/apt/sources.list.d/ubuntu.sources"

# 官方归档与安全服务器的 URI 前缀，切换镜像时一并改写（含 https 变体）
_OFFICIAL_HOSTS = (
    "http://archive.ubuntu.com/ubuntu",
    "https://archive.ubuntu.com/ubuntu",
    "http://security.ubuntu.com/ubuntu",
    "https://security.ubuntu.com/ubuntu",
)


def _rewrite_deb_uri(line: str, mirror: str) -> str:
    """把 deb 行的官方归档/安全服务器 URI 替换为镜像，保留组件/仓库等其余字段。"""
    for host in _OFFICIAL_HOSTS:
        if host in line:
            return line.replace(host, mirror)
    return line


# 「不更改」选项的显示名：选中时跳过换源，保持系统原有 apt 源
_SKIP_LABEL = "不更改"


def _is_skip(cfg) -> bool:
    return getattr(cfg, "APT_MIRROR", None) == _SKIP_LABEL


def _mirror_base(cfg) -> str:
    name = getattr(cfg, "APT_MIRROR", None)
    mirrors = getattr(cfg, "APT_MIRRORS", None)
    if mirrors and name in mirrors:
        return mirrors[name].rstrip("/")
    # 兼容旧 config：直接返回字符串
    url = getattr(cfg, "APT_MIRROR_URL", None)
    if url:
        return url.rstrip("/")
    raise utils.TaskError("未配置 APT_MIRRORS/APT_MIRROR")


def _has_mirror(cfg) -> bool:
    """判断源文件是否已指向配置的镜像（检查生效的 deb / URIs 行）。"""
    mirror = _mirror_base(cfg)
    for path in (_SOURCES_LIST, _SOURCES_DEB822):
        for line in utils.read_lines(path):
            stripped = line.lstrip()
            if not stripped or stripped.startswith("#"):
                continue
            if (stripped.startswith("deb ") or stripped.startswith("URIs:")) and mirror in line:
                return True
    return False


def _is_deb822(codename: str) -> bool:
    return codename in ("noble", "resolute")


class AptMirrorTask(Task):
    id = "apt_mirror"
    name = "切换 apt 源为国内镜像"
    description = "将 apt 源切换为配置的国内镜像（默认清华 TUNA）"
    depends_on = []

    def check(self, cfg, log=None):
        if _is_skip(cfg):
            return True, "已选择不更改源"
        if _has_mirror(cfg):
            return True, "已指向镜像源"
        return False, "未切换镜像源"

    def run(self, cfg, log=None):
        if _is_skip(cfg):
            if log:
                log("⏭ 已选择不更改 apt 源，跳过。")
            return
        codename = utils.detect_codename()
        mirror = _mirror_base(cfg)
        if _is_deb822(codename):
            self._patch_deb822(codename, mirror)
        else:
            self._patch_classic(codename, mirror)

    def _patch_classic(self, codename: str, mirror: str) -> None:
        """22.04 经典格式：改写 /etc/apt/sources.list 中 deb 行的归档/安全服务器地址。"""
        lines = utils.read_lines(_SOURCES_LIST)
        if not lines:
            # 某些镜像默认只有 .list.d 下的源，这里尽量兼容常见归档服务器
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
        utils.backup_write(_SOURCES_LIST, "\n".join(out) + "\n")

    def _patch_deb822(self, codename: str, mirror: str) -> None:
        """24.04/26.04 deb822 格式：改写 URIs: 与 Suites: 字段。"""
        path = _SOURCES_DEB822
        if not os.path.exists(path):
            utils.backup_write(path, _default_deb822(codename, mirror))
            return
        lines = utils.read_lines(path)
        out = []
        for line in lines:
            if line.startswith("URIs:"):
                out.append(f"URIs: {mirror}")
            elif line.startswith("Suites:"):
                # 保留其余套件名，只替换 codename 本身（如 noble -> 保持，其实 mirror 不改变 codename）
                # 这里按需保留原样：codename 不随镜像改变，仅确保存在
                out.append(line)
            else:
                out.append(line)
        utils.backup_write(path, "\n".join(out) + "\n")


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
