"""fzf 安装（apt）。"""

from __future__ import annotations

from ..core.task import CheckResult, Context, Task, task
from ..platform import sys as psys


@task(
    id="fzf",
    name="安装 fzf",
    description="命令行模糊查找工具 fzf（zsh 集成交由 zsh 任务统一写入）",
    depends_on=("apt_mirror",),
)
class FzfTask(Task):
    def check(self, ctx: Context) -> CheckResult:
        if psys.command_exists("fzf"):
            return CheckResult(True, "fzf 已安装")
        return CheckResult(False, "fzf 未安装")

    def run(self, ctx: Context) -> None:
        ctx.apt.install(["fzf"], log=ctx.log.log, tee=ctx.log.stream)
