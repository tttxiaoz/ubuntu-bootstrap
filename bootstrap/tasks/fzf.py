"""fzf 安装 + zsh 集成。"""

from __future__ import annotations

from ..config.schema import Param
from ..core.task import CheckResult, Context, Task, task
from ..platform import sys as psys
from ..platform import user


@task(
    id="fzf",
    name="安装 fzf",
    description="命令行模糊查找工具 fzf（zsh 集成交由 zsh 任务统一写入）",
    depends_on=("apt_mirror",),
    params=[Param("fzf.method", "choice", default="apt", choices=("apt", "github"),
                  label="fzf 安装方式")],
)
class FzfTask(Task):
    def check(self, ctx: Context) -> CheckResult:
        if psys.command_exists("fzf"):
            return CheckResult(True, "fzf 已安装")
        return CheckResult(False, "fzf 未安装")

    def run(self, ctx: Context) -> None:
        method = ctx.config.get("fzf.method")
        if method == "github":
            home = user.real_home()
            dest = f"{home}/.fzf"
            ctx.run_cmd(["git", "clone", "--depth", "1",
                         "https://github.com/junegunn/fzf.git", dest])
            ctx.run_cmd([f"{dest}/install", "--all"])
        else:
            ctx.apt.install(["fzf"], log=ctx.log.log, tee=ctx.log.stream)
