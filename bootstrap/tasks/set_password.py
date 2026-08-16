"""设置当前用户密码（sudo 时为真实调用者，直接 root 时为 root）。

交互式向导会安全地询问密码（不落盘）；--all 非交互时仅当 config.toml 里
显式填写 password.value 才生效，否则跳过并提示。
"""

from __future__ import annotations

from ..config.schema import Param
from ..core.task import CheckResult, Context, Task, task
from ..platform import sys as psys
from ..platform import user


@task(
    id="set_password",
    name="设置用户密码",
    description="为当前用户（sudo 时真实用户 / root 时 root）设置登录密码",
    params=[Param("password.value", "password", default="", label="设置用户密码")],
)
class SetPasswordTask(Task):
    def check(self, ctx: Context) -> CheckResult:
        u = user.real_user()
        status = self._password_status(u)
        if status == "P":
            return CheckResult(True, f"用户 {u} 已有可用密码")
        return CheckResult(False, f"用户 {u} 密码未设置或已锁定（{status or '未知'}）")

    def run(self, ctx: Context) -> None:
        u = user.real_user()
        password = ctx.config.get("password.value") or ""
        if not password:
            ctx.log.log("⚠️ 未提供用户密码，跳过设置。可在 config.toml 设 password.value，"
                        "或交互式运行本工具。")
            return
        # 密码经 stdin 传入，不会出现在命令行/日志中
        psys.run_cmd(["chpasswd"], input_text=f"{u}:{password}\n", log=ctx.log.log)
        psys.run_cmd(["passwd", "-u", u], check=False, log=ctx.log.log)
        ctx.log.log(f"✅ 已设置用户 {u} 的密码")

    @staticmethod
    def _password_status(u: str) -> str:
        """passwd -S 的第二个字段：P=可用 / L=锁定 / NP=无密码。"""
        result = psys.run_cmd(["passwd", "-S", u], check=False, capture=True)
        parts = (result.stdout or "").split()
        return parts[1] if len(parts) >= 2 else ""
