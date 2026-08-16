"""系统更新：apt-get update + upgrade。"""

from __future__ import annotations

from ..core.task import CheckResult, Context, Task, task


@task(
    id="system_update",
    name="更新系统",
    description="apt-get update + upgrade",
    depends_on=("apt_mirror",),
)
class SystemUpdateTask(Task):
    def check(self, ctx: Context) -> CheckResult:
        # 无持久状态，非幂等：每次运行都会执行 update + upgrade
        return CheckResult(False, "非幂等，每次运行均执行 update + upgrade")

    def run(self, ctx: Context) -> None:
        ctx.run_cmd(["apt-get", "update"])
        ctx.run_cmd(["apt-get", "upgrade", "-y", "--fix-missing"])
