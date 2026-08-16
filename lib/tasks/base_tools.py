"""基础工具安装（候选清单可多选，空=安装全部）。"""

from __future__ import annotations

from .base import Task
from .. import utils


def _selected(cfg) -> list:
    """实际要安装的包：BASE_PACKAGES_SELECTED 非空用它，否则装全部候选。"""
    sel = getattr(cfg, "BASE_PACKAGES_SELECTED", None)
    return list(sel) if sel else list(cfg.BASE_PACKAGES)


class BaseToolsTask(Task):
    id = "base_tools"
    name = "安装基础工具"
    description = "git / curl / wget / htop / build-essential 等（向导可多选）"
    depends_on = ["apt_mirror"]

    def check(self, cfg, log=None):
        missing = [p for p in _selected(cfg) if not utils.package_installed(p)]
        if not missing:
            return True, "已全部安装"
        return False, f"缺少 {len(missing)} 个包"

    def run(self, cfg, log=None):
        missing = [p for p in _selected(cfg) if not utils.package_installed(p)]
        if missing:
            utils.apt_install(missing, log=log)
