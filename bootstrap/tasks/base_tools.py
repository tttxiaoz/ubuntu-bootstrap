"""基础工具安装（候选清单可多选，空=安装全部）。"""

from __future__ import annotations

from ..config.schema import Param
from ..core.task import CheckResult, Context, Task, task
from ..platform import sys as psys


def _selected(config) -> list:
    """实际要安装的包：base_tools.selected 非空用它，否则装全部候选。"""
    sel = config.get("base_tools.selected") or []
    return list(sel) if sel else list(config.get("base_tools.packages") or [])


@task(
    id="base_tools",
    name="安装基础工具",
    description="git / curl / wget / htop / build-essential 等（向导可多选）",
    depends_on=("apt_mirror",),
    params=[Param("base_tools.selected", "multi", default=[],
                  choices="config:base_tools.packages", label="要安装的基础工具")],
)
class BaseToolsTask(Task):
    def check(self, ctx: Context) -> CheckResult:
        missing = [p for p in _selected(ctx.config) if not psys.package_installed(p)]
        if not missing:
            return CheckResult(True, "已全部安装")
        return CheckResult(False, f"缺少 {len(missing)} 个包")

    def run(self, ctx: Context) -> None:
        missing = [p for p in _selected(ctx.config) if not psys.package_installed(p)]
        if missing:
            ctx.apt.install(missing, log=ctx.log.log, tee=ctx.log.stream)
