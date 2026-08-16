"""系统更新：apt-get update + upgrade。"""

from __future__ import annotations

from .base import Task
from .. import utils


class SystemUpdateTask(Task):
    id = "system_update"
    name = "更新系统"
    description = "apt-get update + upgrade"
    depends_on = ["apt_mirror"]

    def check(self, cfg, log=None):
        # 无持久状态，非幂等：每次运行都会执行 update + upgrade
        return False, "非幂等，每次运行均执行 update + upgrade"

    def run(self, cfg, log=None):
        utils.run_cmd(["apt-get", "update"], log=log)
        utils.run_cmd(["apt-get", "upgrade", "-y", "--fix-missing"], log=log)
