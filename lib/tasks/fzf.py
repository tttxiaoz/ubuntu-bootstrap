"""fzf 安装 + zsh 集成。"""

from __future__ import annotations

from .base import Task
from .. import utils


class FzfTask(Task):
    id = "fzf"
    name = "安装 fzf"
    description = "命令行模糊查找工具 fzf（zsh 集成交由 zsh 任务统一写入）"
    depends_on = ["apt_mirror"]

    def check(self, cfg, log=None):
        if utils.command_exists("fzf"):
            return True, "fzf 已安装"
        return False, "fzf 未安装"

    def run(self, cfg, log=None):
        method = getattr(cfg, "FZF_INSTALL_METHOD", "apt")
        if method == "github":
            utils.run_cmd(
                ["git", "clone", "--depth", "1", "https://github.com/junegunn/fzf.git",
                 f"/home/{utils.real_user()}/.fzf"],
                log=log,
            )
            utils.run_cmd(
                [f"/home/{utils.real_user()}/.fzf/install", "--all"],
                log=log,
            )
        else:
            utils.apt_install(["fzf"], log=log)
