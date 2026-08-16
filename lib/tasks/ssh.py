"""SSH：安装启动 + 密码认证 + 允许 root + 重启生效验证 + 防火墙放行 22。"""

from __future__ import annotations

import os
import re

from .base import Task
from .. import utils

# 用 drop-in 覆盖 cloud-init 等可能写入的默认值。/etc/ssh/sshd_config.d 按字典序加载，
# 99- 前缀保证排在 50-cloud-init.conf 之后、生效优先级最高。
_SSHD_DROPIN = "/etc/ssh/sshd_config.d/99-bootstrap.conf"
_SSH_PORT = 22


class SshTask(Task):
    id = "ssh"
    name = "配置 SSH 登录"
    description = "安装 openssh-server，按配置设置密码认证与 root 登录，重启生效并放行 22 端口"
    depends_on = ["apt_mirror", "set_password"]

    def check(self, cfg, log=None):
        if not utils.package_installed("openssh-server"):
            return False, "openssh-server 未安装"
        if not self._service_active():
            return False, "sshd 未运行"
        if not self._config_ok(cfg):
            return False, "sshd 配置待修改"
        return True, "SSH 已就绪"

    def run(self, cfg, log=None):
        if not utils.package_installed("openssh-server"):
            utils.apt_install(["openssh-server"], log=log)

        want_pass = getattr(cfg, "SSH_PASSWORD_AUTH", "yes")
        want_root = getattr(cfg, "SSH_PERMIT_ROOT_LOGIN", "yes")

        self._warn_if_insecure(want_pass, want_root, log)

        self._ensure_config("PasswordAuthentication", want_pass, log)
        self._ensure_config("PermitRootLogin", want_root, log)

        # 语法校验通过才重启/启动
        utils.run_cmd(["sshd", "-t"], log=log)
        self._start_service(log)
        self._restart_service(log)

        # 验证生效
        if self._port_listening(_SSH_PORT):
            if log:
                log(f"✅ SSH 已监听 {_SSH_PORT} 端口")
        elif log:
            log(f"⚠️ 未检测到 {_SSH_PORT} 端口监听，请用 systemctl status ssh 排查")

        # 防火墙放行
        if utils.command_exists("ufw"):
            utils.run_cmd(["ufw", "allow", f"{_SSH_PORT}/tcp"], check=False, log=log)
        elif log:
            log(f"提示：未检测到 ufw，若为云服务器请到控制台安全组放行 {_SSH_PORT} 端口")

    def _warn_if_insecure(self, want_pass: str, want_root: str, log) -> None:
        """密码认证 / root 直接登录开启时给出醒目安全提醒。"""
        risky = []
        if want_pass == "yes":
            risky.append("密码认证")
        if want_root == "yes":
            risky.append("root 直接登录")
        if not risky:
            return
        msg = ("⚠️ 安全提醒：本次将开启 SSH " + " + ".join(risky)
               + "。公网暴露下有被暴力破解的风险，建议改用密钥登录，"
                 "并在 config.py 设 SSH_PASSWORD_AUTH / SSH_PERMIT_ROOT_LOGIN 为 no。")
        if log:
            log(msg)
        else:
            print(msg)

    def _ensure_config(self, key: str, value: str, log) -> None:
        """把 key value 写入高优先级 drop-in，不触碰主 sshd_config，避免影响其他配置。"""
        lines = utils.read_lines(_SSHD_DROPIN)
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
        utils.backup_write(_SSHD_DROPIN, "\n".join(out) + "\n")

    def _config_ok(self, cfg) -> bool:
        """用 sshd -T 解析生效配置（含 drop-in），避免漏判被覆盖的值。"""
        want_pass = getattr(cfg, "SSH_PASSWORD_AUTH", "yes")
        want_root = getattr(cfg, "SSH_PERMIT_ROOT_LOGIN", "yes")
        active = self._effective_config()
        return (active.get("passwordauthentication") == want_pass
                and active.get("permitrootlogin") == want_root)

    def _start_service(self, log) -> None:
        """启用并启动 ssh 服务（systemctl 优先，容器环境降级 service）。"""
        if utils.command_exists("systemctl"):
            utils.run_cmd(["systemctl", "enable", "--now", "ssh"], check=False, log=log)
        elif utils.command_exists("service"):
            utils.run_cmd(["service", "ssh", "start"], check=False, log=log)

    def _restart_service(self, log) -> None:
        """重启 ssh 服务使配置生效（systemctl → service 逐级降级）。"""
        if utils.command_exists("systemctl"):
            r = utils.run_cmd(["systemctl", "restart", "ssh"], check=False, log=log)
            if r.returncode == 0:
                return
            if log:
                log("systemctl restart ssh 失败，尝试 service ...")
        if utils.command_exists("service"):
            utils.run_cmd(["service", "ssh", "restart"], log=log)

    @staticmethod
    def _effective_config() -> dict:
        try:
            result = utils.run_cmd(["sshd", "-T"], check=False, capture=True)
        except utils.TaskError:
            return {}
        active = {}
        for line in (result.stdout or "").splitlines():
            if " " in line:
                k, v = line.split(None, 1)
                active[k] = v
        return active

    @staticmethod
    def _service_active() -> bool:
        if utils.command_exists("systemctl"):
            r = utils.run_cmd(["systemctl", "is-active", "ssh"], check=False, capture=True)
            if (r.stdout or "").strip() == "active":
                return True
        # 无 systemctl 时回退为端口监听检测
        return SshTask._port_listening(_SSH_PORT)

    @staticmethod
    def _port_listening(port: int) -> bool:
        if utils.command_exists("ss"):
            r = utils.run_cmd(["ss", "-tln"], check=False, capture=True)
        elif utils.command_exists("netstat"):
            r = utils.run_cmd(["netstat", "-tln"], check=False, capture=True)
        else:
            return False
        return any(re.search(rf":{port}\b", line)
                   for line in (r.stdout or "").splitlines())
