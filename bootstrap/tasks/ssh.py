"""SSH：安装启动 + 密码认证 + 允许 root + 重启生效验证 + 防火墙放行 22。"""

from __future__ import annotations

import os
import re

from ..config.schema import Param
from ..core.task import CheckResult, Context, Task, task
from ..platform import fs
from ..platform import sys as psys

# 用 drop-in 覆盖 cloud-init 等可能写入的默认值。/etc/ssh/sshd_config.d 按字典序加载，
# 99- 前缀保证排在 50-cloud-init.conf 之后、生效优先级最高。
_SSHD_DROPIN = "/etc/ssh/sshd_config.d/99-bootstrap.conf"
_SSH_PORT = 22


def _yn(value: bool) -> str:
    return "yes" if value else "no"


@task(
    id="ssh",
    name="配置 SSH 登录",
    description="安装 openssh-server，按配置设置密码认证与 root 登录，重启生效并放行 22 端口",
    depends_on=("apt_mirror", "set_password"),
    params=[
        Param("ssh.password_auth", "bool", default=True, label="SSH 密码认证"),
        Param("ssh.permit_root_login", "bool", default=True, label="允许 root 登录"),
    ],
)
class SshTask(Task):
    def check(self, ctx: Context) -> CheckResult:
        if not psys.package_installed("openssh-server"):
            return CheckResult(False, "openssh-server 未安装")
        if not self._service_active():
            return CheckResult(False, "sshd 未运行")
        if not self._config_ok(ctx.config):
            return CheckResult(False, "sshd 配置待修改")
        return CheckResult(True, "SSH 已就绪")

    def run(self, ctx: Context) -> None:
        if not psys.package_installed("openssh-server"):
            ctx.apt.install(["openssh-server"], log=ctx.log.log, tee=ctx.log.stream)

        want_pass = ctx.config.get("ssh.password_auth")
        want_root = ctx.config.get("ssh.permit_root_login")

        self._warn_if_insecure(want_pass, want_root, ctx.log)

        self._ensure_config("PasswordAuthentication", _yn(want_pass), ctx.log)
        self._ensure_config("PermitRootLogin", _yn(want_root), ctx.log)

        # 语法校验通过才重启/启动
        ctx.run_cmd(["sshd", "-t"])
        self._start_service(ctx)
        self._restart_service(ctx)

        # 验证生效
        if self._port_listening(_SSH_PORT):
            ctx.log.log(f"✅ SSH 已监听 {_SSH_PORT} 端口")
        else:
            ctx.log.log(f"⚠️ 未检测到 {_SSH_PORT} 端口监听，请用 systemctl status ssh 排查")

        # 防火墙放行
        if psys.command_exists("ufw"):
            ctx.run_cmd(["ufw", "allow", f"{_SSH_PORT}/tcp"], check=False)
        else:
            ctx.log.log(f"提示：未检测到 ufw，若为云服务器请到控制台安全组放行 {_SSH_PORT} 端口")

    def _warn_if_insecure(self, want_pass: bool, want_root: bool, log) -> None:
        """密码认证 / root 直接登录开启时给出醒目安全提醒。"""
        risky = []
        if want_pass:
            risky.append("密码认证")
        if want_root:
            risky.append("root 直接登录")
        if not risky:
            return
        msg = ("⚠️ 安全提醒：本次将开启 SSH " + " + ".join(risky)
               + "。公网暴露下有被暴力破解的风险，建议改用密钥登录，"
                 "并在 config.toml 把 ssh.password_auth / ssh.permit_root_login 设为 false。")
        log.log(msg)

    def _ensure_config(self, key: str, value: str, log) -> None:
        """把 key value 写入高优先级 drop-in，不触碰主 sshd_config。"""
        lines = fs.read_lines(_SSHD_DROPIN)
        found = False
        out = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                out.append(line)
                continue
            if stripped.split(None, 1)[0] == key:
                out.append(f"{key} {value}")
                found = True
            else:
                out.append(line)
        if not found:
            out.append(f"{key} {value}")
        os.makedirs(os.path.dirname(_SSHD_DROPIN), exist_ok=True)
        fs.backup_write(_SSHD_DROPIN, "\n".join(out) + "\n")

    def _config_ok(self, config) -> bool:
        """用 sshd -T 解析生效配置（含 drop-in），避免漏判被覆盖的值。"""
        want_pass = _yn(config.get("ssh.password_auth"))
        want_root = _yn(config.get("ssh.permit_root_login"))
        active = self._effective_config()
        return (active.get("passwordauthentication") == want_pass
                and active.get("permitrootlogin") == want_root)

    def _start_service(self, ctx: Context) -> None:
        if psys.command_exists("systemctl"):
            ctx.run_cmd(["systemctl", "enable", "--now", "ssh"], check=False)
        elif psys.command_exists("service"):
            ctx.run_cmd(["service", "ssh", "start"], check=False)

    def _restart_service(self, ctx: Context) -> None:
        if psys.command_exists("systemctl"):
            r = ctx.run_cmd(["systemctl", "restart", "ssh"], check=False)
            if r.returncode == 0:
                return
            ctx.log.log("systemctl restart ssh 失败，尝试 service ...")
        if psys.command_exists("service"):
            ctx.run_cmd(["service", "ssh", "restart"])

    @staticmethod
    def _effective_config() -> dict:
        try:
            result = psys.run_cmd(["sshd", "-T"], check=False, capture=True)
        except psys.TaskError:
            return {}
        active = {}
        for line in (result.stdout or "").splitlines():
            if " " in line:
                k, v = line.split(None, 1)
                active[k] = v
        return active

    @staticmethod
    def _service_active() -> bool:
        if psys.command_exists("systemctl"):
            r = psys.run_cmd(["systemctl", "is-active", "ssh"], check=False, capture=True)
            if (r.stdout or "").strip() == "active":
                return True
        # 无 systemctl 时回退为端口监听检测
        return SshTask._port_listening(_SSH_PORT)

    @staticmethod
    def _port_listening(port: int) -> bool:
        if psys.command_exists("ss"):
            r = psys.run_cmd(["ss", "-tln"], check=False, capture=True)
        elif psys.command_exists("netstat"):
            r = psys.run_cmd(["netstat", "-tln"], check=False, capture=True)
        else:
            return False
        return any(re.search(rf":{port}\b", line)
                   for line in (r.stdout or "").splitlines())
