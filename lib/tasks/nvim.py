"""neovim 安装 + 将 vi/vim 指向 nvim。"""

from __future__ import annotations

from .base import Task
from .. import utils


class NvimTask(Task):
    id = "nvim"
    name = "安装 neovim 并设为默认 vi/vim"
    description = "安装 neovim，并将 vi/vim 指向 nvim"
    depends_on = ["apt_mirror"]

    def check(self, cfg, log=None):
        if not utils.command_exists("nvim"):
            return False, "nvim 未安装"
        if not (utils.command_exists("vi") and utils.command_exists("vim")):
            return False, "vi/vim 尚未指向 nvim"
        return True, "nvim 已就绪"

    def run(self, cfg, log=None):
        if not utils.command_exists("nvim"):
            self._install_nvim(cfg, log)

        nvim = utils.run_cmd(["which", "nvim"], capture=True).stdout.strip()
        # update-alternatives 提升 nvim 优先级
        utils.run_cmd(["update-alternatives", "--install", "/usr/bin/vi", "vi", nvim, "60"], log=log)
        utils.run_cmd(["update-alternatives", "--install", "/usr/bin/vim", "vim", nvim, "60"], log=log)
        utils.run_cmd(["update-alternatives", "--set", "vi", nvim], check=False, log=log)
        utils.run_cmd(["update-alternatives", "--set", "vim", nvim], check=False, log=log)

        # shell 层别名兜底
        self._write_alias(cfg, log)

    def _install_nvim(self, cfg, log=None) -> None:
        method = getattr(cfg, "NEOVIM_INSTALL_METHOD", "apt")
        if method == "github":
            # 拉取最新 release tarball 解压到 /opt/nvim
            tarball = "nvim-linux-x86_64.tar.gz"
            url = f"https://github.com/neovim/neovim/releases/latest/download/{tarball}"
            utils.run_cmd(["curl", "-fsSL", "-o", f"/tmp/{tarball}", url], log=log)
            utils.run_cmd(["mkdir", "-p", "/opt/nvim"], log=log)
            utils.run_cmd(["tar", "-xzf", f"/tmp/{tarball}", "-C", "/opt/nvim", "--strip-components=1"], log=log)
            utils.run_cmd(["ln", "-sf", "/opt/nvim/bin/nvim", "/usr/local/bin/nvim"], log=log)
        else:
            utils.apt_install(["neovim"], log=log)

    def _write_alias(self, cfg, log=None) -> None:
        home = utils.real_home()
        zshrc = f"{home}/.zshrc"
        if not utils.command_exists("zsh"):
            return  # zsh 尚未安装，别名交由 zsh 任务写入
        lines = utils.read_lines(zshrc)
        needs_vi = not any("alias vi=" in l for l in lines)
        needs_vim = not any("alias vim=" in l for l in lines)
        if not (needs_vi or needs_vim):
            return
        utils.backup_file(zshrc)
        with open(zshrc, "a", encoding="utf-8") as fh:
            if needs_vi:
                fh.write("alias vi='nvim'\n")
            if needs_vim:
                fh.write("alias vim='nvim'\n")
