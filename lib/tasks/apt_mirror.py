"""apt 源切换：支持 22.04（sources.list）与 24.04/26.04（deb822 .sources）两种格式。"""

from __future__ import annotations

import os

from .base import Task
from .. import utils

_SOURCES_LIST = "/etc/apt/sources.list"
_SOURCES_DEB822 = "/etc/apt/sources.list.d/ubuntu.sources"


def _mirror_base(cfg) -> str:
    url = cfg.APT_MIRROR_URL.rstrip("/")
    return url


def _has_mirror(cfg) -> bool:
    """判断源文件是否已指向配置的镜像。"""
    mirror = _mirror_base(cfg)
    for path in (_SOURCES_LIST, _SOURCES_DEB822):
        for line in utils.read_lines(path):
            if line.lstrip().startswith("#"):
                continue
            if mirror in line:
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
        if _has_mirror(cfg):
            return True, "已指向镜像源"
        return False, "未切换镜像源"

    def run(self, cfg, log=None):
        codename = utils.detect_codename()
        mirror = _mirror_base(cfg)
        if _is_deb822(codename):
            self._patch_deb822(codename, mirror)
        else:
            self._patch_classic(codename, mirror)

    def _patch_classic(self, codename: str, mirror: str) -> None:
        """22.04 经典格式：改写 /etc/apt/sources.list 中 deb 行。"""
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
                # 仅替换归档服务器地址，保留组件/仓库等其余字段
                out.append(line.replace("http://archive.ubuntu.com/ubuntu",
                                        mirror).replace("https://archive.ubuntu.com/ubuntu",
                                                        mirror))
            elif stripped.startswith("deb ") and mirror in line:
                out.append(line)  # 已经是镜像，保持
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
        f"URIs: http://security.ubuntu.com/ubuntu/\n"
        f"Suites: {codename}-security\n"
        "Components: main restricted universe multiverse\n"
        "Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n"
    )
