"""基础工具安装。"""

from __future__ import annotations

from .base import Task
from .. import utils


class BaseToolsTask(Task):
    id = "base_tools"
    name = "安装基础工具"
    description = "git / curl / wget / htop / build-essential 等"
    depends_on = ["apt_mirror"]

    def check(self, cfg, log=None):
        missing = [p for p in cfg.BASE_PACKAGES if not utils.package_installed(p)]
        if not missing:
            return True, "已全部安装"
        return False, f"缺少 {len(missing)} 个包"

    def run(self, cfg, log=None):
        missing = [p for p in cfg.BASE_PACKAGES if not utils.package_installed(p)]
        if missing:
            utils.apt_install(missing, log=log)
