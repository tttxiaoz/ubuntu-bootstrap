"""SSH：安装启动 + 密码认证 + 允许 root + 防火墙放行 22。"""

from __future__ import annotations

from .base import Task
from .. import utils

_SSHD_CONFIG = "/etc/ssh/sshd_config"


class SshTask(Task):
    id = "ssh"
    name = "配置 SSH 密码登录"
    description = "安装 openssh-server，开启密码认证与 root 登录，放行 22 端口"
    depends_on = ["apt_mirror"]

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
        utils.run_cmd(["systemctl", "enable", "--now", "ssh"], log=log)

        self._ensure_config(cfg, "PasswordAuthentication",
                            getattr(cfg, "SSH_PASSWORD_AUTH", "yes"), log)
        self._ensure_config(cfg, "PermitRootLogin",
                            getattr(cfg, "SSH_PERMIT_ROOT_LOGIN", "yes"), log)

        # 语法校验通过才重启
        utils.run_cmd(["sshd", "-t"], log=log)
        utils.run_cmd(["systemctl", "restart", "ssh"], log=log)

        # 防火墙放行
        if utils.command_exists("ufw"):
            utils.run_cmd(["ufw", "allow", "22/tcp"], check=False, log=log)
        else:
            if log:
                log("提示：未检测到 ufw，若为云服务器请到控制台安全组放行 22 端口")

    def _ensure_config(self, cfg, key: str, value: str, log) -> None:
        lines = utils.read_lines(_SSHD_CONFIG)
        found = False
        out = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#") and stripped.lstrip("#").strip().startswith(key):
                # 打开被注释的行并设为目标值
                out.append(f"{key} {value}")
                found = True
            elif stripped.startswith(key):
                out.append(f"{key} {value}")
                found = True
            else:
                out.append(line)
        if not found:
            out.append(f"{key} {value}")
        utils.backup_write(_SSHD_CONFIG, "\n".join(out) + "\n")

    def _config_ok(self, cfg) -> bool:
        lines = utils.read_lines(_SSHD_CONFIG)
        active = {}
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#") or not stripped:
                continue
            if " " in stripped:
                k, v = stripped.split(None, 1)
                active[k] = v
        want_pass = getattr(cfg, "SSH_PASSWORD_AUTH", "yes")
        want_root = getattr(cfg, "SSH_PERMIT_ROOT_LOGIN", "yes")
        return active.get("PasswordAuthentication") == want_pass and active.get("PermitRootLogin") == want_root

    @staticmethod
    def _service_active() -> bool:
        result = utils.run_cmd(["systemctl", "is-active", "ssh"], check=False, capture=True)
        return (result.stdout or "").strip() == "active"
