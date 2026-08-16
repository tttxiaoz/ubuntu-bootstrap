"""ssh 任务的 drop-in 写入与生效配置判定测试。"""

from __future__ import annotations

from types import SimpleNamespace

from lib.tasks import ssh as ssh_module
from lib.tasks.ssh import SshTask


def _cfg(pass_auth="yes", root_login="no"):
    return SimpleNamespace(SSH_PASSWORD_AUTH=pass_auth, SSH_PERMIT_ROOT_LOGIN=root_login)


def test_config_ok(monkeypatch):
    t = SshTask()
    monkeypatch.setattr(
        t, "_effective_config",
        lambda: {"passwordauthentication": "yes", "permitrootlogin": "no"},
    )
    assert t._config_ok(_cfg("yes", "no")) is True


def test_config_not_ok_root_login(monkeypatch):
    t = SshTask()
    monkeypatch.setattr(
        t, "_effective_config",
        lambda: {"passwordauthentication": "yes", "permitrootlogin": "no"},
    )
    assert t._config_ok(_cfg("yes", "yes")) is False


def test_ensure_config_writes_dropin(tmp_path, monkeypatch):
    monkeypatch.setattr(ssh_module, "_SSHD_DROPIN", str(tmp_path / "99-bootstrap.conf"))
    SshTask()._ensure_config("PasswordAuthentication", "no", log=None)
    text = (tmp_path / "99-bootstrap.conf").read_text()
    assert "PasswordAuthentication no" in text


def test_ensure_config_updates_existing_key(tmp_path, monkeypatch):
    dropin = tmp_path / "99-bootstrap.conf"
    dropin.write_text("PasswordAuthentication yes\nPermitRootLogin yes\n")
    monkeypatch.setattr(ssh_module, "_SSHD_DROPIN", str(dropin))
    SshTask()._ensure_config("PasswordAuthentication", "no", log=None)
    text = dropin.read_text()
    assert "PasswordAuthentication no" in text
    assert "PasswordAuthentication yes" not in text
    assert "PermitRootLogin yes" in text
