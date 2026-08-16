"""locale 与时区设置。"""

from __future__ import annotations

from ..config.schema import Param
from ..core.task import CheckResult, Context, Task, task
from ..platform import fs
from ..platform import sys as psys


@task(
    id="locale_timezone",
    name="设置时区与 locale",
    description="时区设为配置值（默认 Asia/Shanghai），locale 设为 zh_CN.UTF-8",
    depends_on=("apt_mirror",),
    params=[
        Param("system.timezone", "choice", default="Asia/Shanghai",
              choices="config:system.timezones", label="时区"),
        Param("system.locale", "choice", default="zh_CN.UTF-8",
              choices="config:system.locales", label="系统语言"),
    ],
)
class LocaleTimezoneTask(Task):
    def check(self, ctx: Context) -> CheckResult:
        locale = ctx.config.get("system.locale")
        tz = ctx.config.get("system.timezone")
        locale_ok = self._locale_ready(locale)
        tz_ok = self._timezone_ready(tz)
        if locale_ok and tz_ok:
            return CheckResult(True, f"已设置 {locale} / {tz}")
        note = (f"locale: {'已' if locale_ok else '未'}配置，"
                f"时区: {'已' if tz_ok else '未'}配置")
        return CheckResult(False, note)

    def run(self, ctx: Context) -> None:
        locale = ctx.config.get("system.locale")
        tz = ctx.config.get("system.timezone")
        if not self._locale_ready(locale):
            if not psys.package_installed("language-pack-zh-hans"):
                ctx.apt.install(["language-pack-zh-hans"], log=ctx.log.log, tee=ctx.log.stream)
            ctx.run_cmd(["locale-gen", locale])
            ctx.run_cmd(["update-locale", f"LANG={locale}"])
        if not self._timezone_ready(tz):
            if psys.command_exists("timedatectl"):
                ctx.run_cmd(["timedatectl", "set-timezone", tz])
            else:
                ctx.run_cmd(["ln", "-sf", f"/usr/share/zoneinfo/{tz}", "/etc/localtime"])

    @staticmethod
    def _locale_ready(locale: str) -> bool:
        result = psys.run_cmd(["locale", "-a"], check=False, capture=True)
        return locale in (result.stdout or "")

    @staticmethod
    def _timezone_ready(tz: str) -> bool:
        if psys.command_exists("timedatectl"):
            result = psys.run_cmd(["timedatectl"], check=False, capture=True)
            return tz in (result.stdout or "")
        # 回退：读 /etc/timezone
        return any(tz in line for line in fs.read_lines("/etc/timezone"))
