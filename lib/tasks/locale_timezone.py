"""locale 与时区设置。"""

from __future__ import annotations

from .base import Task
from .. import utils


class LocaleTimezoneTask(Task):
    id = "locale_timezone"
    name = "设置时区与 locale"
    description = "时区设为配置值（默认 Asia/Shanghai），locale 设为 zh_CN.UTF-8"
    depends_on = ["apt_mirror"]

    def check(self, cfg, log=None):
        locale_ok = self._locale_ready(cfg.LOCALE)
        tz_ok = self._timezone_ready(cfg.TIMEZONE)
        if locale_ok and tz_ok:
            return True, f"已设置 {cfg.LOCALE} / {cfg.TIMEZONE}"
        return False, f"locale: {'已' if locale_ok else '未'}配置，时区: {'已' if tz_ok else '未'}配置"

    def run(self, cfg, log=None):
        if not self._locale_ready(cfg.LOCALE):
            if not utils.package_installed("language-pack-zh-hans"):
                utils.apt_install(["language-pack-zh-hans"], log=log)
            utils.run_cmd(["locale-gen", cfg.LOCALE], log=log)
            utils.run_cmd(["update-locale", f"LANG={cfg.LOCALE}"], log=log)
        if not self._timezone_ready(cfg.TIMEZONE):
            if utils.command_exists("timedatectl"):
                utils.run_cmd(["timedatectl", "set-timezone", cfg.TIMEZONE], log=log)
            else:
                utils.run_cmd(
                    ["ln", "-sf", f"/usr/share/zoneinfo/{cfg.TIMEZONE}", "/etc/localtime"],
                    log=log,
                )

    @staticmethod
    def _locale_ready(locale: str) -> bool:
        result = utils.run_cmd(["locale", "-a"], check=False, capture=True)
        return locale in (result.stdout or "")

    @staticmethod
    def _timezone_ready(tz: str) -> bool:
        if utils.command_exists("timedatectl"):
            result = utils.run_cmd(["timedatectl"], check=False, capture=True)
            return tz in (result.stdout or "")
        # 回退：读 /etc/timezone
        return any(tz in l for l in utils.read_lines("/etc/timezone"))
