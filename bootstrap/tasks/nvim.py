"""neovim 安装 + 将 vi/vim 指向 nvim。"""

from __future__ import annotations

import shutil

from ..config.schema import Param
from ..core.task import CheckResult, Context, Task, task
from ..platform import fs, user
from ..platform import sys as psys


@task(
    id="nvim",
    name="安装 neovim 并设为默认 vi/vim",
    description="安装 neovim，并将 vi/vim 指向 nvim",
    depends_on=("apt_mirror",),
    params=[Param("nvim.method", "choice", default="apt", choices=("apt", "github"),
                  label="neovim 安装方式")],
)
class NvimTask(Task):
    def check(self, ctx: Context) -> CheckResult:
        if not psys.command_exists("nvim"):
            return CheckResult(False, "nvim 未安装")
        if not (psys.command_exists("vi") and psys.command_exists("vim")):
            return CheckResult(False, "vi/vim 尚未指向 nvim")
        return CheckResult(True, "nvim 已就绪")

    def run(self, ctx: Context) -> None:
        if not psys.command_exists("nvim"):
            self._install_nvim(ctx)

        nvim = shutil.which("nvim")
        if not nvim:
            raise psys.TaskError("安装后仍找不到 nvim 可执行文件")
        # update-alternatives 提升 nvim 优先级
        ctx.run_cmd(["update-alternatives", "--install", "/usr/bin/vi", "vi", nvim, "60"])
        ctx.run_cmd(["update-alternatives", "--install", "/usr/bin/vim", "vim", nvim, "60"])
        ctx.run_cmd(["update-alternatives", "--set", "vi", nvim], check=False)
        ctx.run_cmd(["update-alternatives", "--set", "vim", nvim], check=False)

        self._write_alias(ctx)

    def _install_nvim(self, ctx: Context) -> None:
        method = ctx.config.get("nvim.method")
        if method == "github":
            arch = psys.detect_arch()
            tarball = f"nvim-linux-{arch}.tar.gz"
            url = f"https://github.com/neovim/neovim/releases/latest/download/{tarball}"
            ctx.run_cmd(["curl", "-fsSL", "-o", f"/tmp/{tarball}", url])
            ctx.run_cmd(["mkdir", "-p", "/opt/nvim"])
            ctx.run_cmd(["tar", "-xzf", f"/tmp/{tarball}", "-C", "/opt/nvim",
                         "--strip-components=1"])
            ctx.run_cmd(["ln", "-sf", "/opt/nvim/bin/nvim", "/usr/local/bin/nvim"])
        else:
            ctx.apt.install(["neovim"], log=ctx.log.log, tee=ctx.log.stream)

    def _write_alias(self, ctx: Context) -> None:
        home = user.real_home()
        zshrc = f"{home}/.zshrc"
        if not psys.command_exists("zsh"):
            return  # zsh 尚未安装，别名交由 zsh 任务写入
        lines = fs.read_lines(zshrc)
        needs_vi = not any("alias vi=" in line for line in lines)
        needs_vim = not any("alias vim=" in line for line in lines)
        if not (needs_vi or needs_vim):
            return
        fs.backup_file(zshrc)
        with open(zshrc, "a", encoding="utf-8") as fh:
            if needs_vi:
                fh.write("alias vi='nvim'\n")
            if needs_vim:
                fh.write("alias vim='nvim'\n")
