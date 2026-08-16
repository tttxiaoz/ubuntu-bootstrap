"""设置当前用户密码（sudo 时为真实调用者，直接 root 时为 root）。

交互式向导会安全地询问密码（不落盘）；--all 非交互时仅当 config.py 里
显式填写 USER_PASSWORD 才生效，否则跳过并提示。
"""

from __future__ import annotations

from .base import Task
from .. import utils


class SetPasswordTask(Task):
    id = "set_password"
    name = "设置用户密码"
    description = "为当前用户（sudo 时真实用户 / root 时 root）设置登录密码"
    depends_on = []

    def check(self, cfg, log=None):
        user = utils.real_user()
        status = self._password_status(user)
        if status == "P":
            return True, f"用户 {user} 已有可用密码"
        return False, f"用户 {user} 密码未设置或已锁定（{status or '未知'}）"

    def run(self, cfg, log=None):
        user = utils.real_user()
        password = getattr(cfg, "USER_PASSWORD", "") or ""
        if not password:
            msg = ("⚠️ 未提供用户密码，跳过设置。"
                   "可在 config.py 设 USER_PASSWORD，或交互式运行本工具。")
            if log:
                log(msg)
            else:
                print(msg)
            return
        # 密码经 stdin 传入，不会出现在命令行/日志中
        utils.run_cmd(["chpasswd"], input_text=f"{user}:{password}\n", log=log)
        # 若账号曾被锁定则解锁
        utils.run_cmd(["passwd", "-u", user], check=False, log=log)
        if log:
            log(f"✅ 已设置用户 {user} 的密码")
        else:
            print(f"✅ 已设置用户 {user} 的密码")

    @staticmethod
    def _password_status(user: str) -> str:
        """passwd -S 的第二个字段：P=可用 / L=锁定 / NP=无密码。"""
        result = utils.run_cmd(["passwd", "-S", user], check=False, capture=True)
        parts = (result.stdout or "").split()
        return parts[1] if len(parts) >= 2 else ""
