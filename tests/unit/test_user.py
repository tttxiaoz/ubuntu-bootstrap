"""platform.user 真实用户识别测试。"""

from __future__ import annotations

from bootstrap.platform import user


def test_real_home_uses_pwd_database(monkeypatch):
    import pwd

    monkeypatch.setenv("SUDO_USER", "nobody")
    assert user.real_home() == pwd.getpwnam("nobody").pw_dir
