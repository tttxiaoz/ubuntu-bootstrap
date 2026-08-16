"""utils 纯函数与文件辅助函数测试。"""

from __future__ import annotations

from lib import utils


def test_replace_or_append_replaces(tmp_path):
    p = tmp_path / "zshrc"
    p.write_text('plugins=(git)\nZSH_THEME="robbyrussell"\n')
    utils.replace_or_append(str(p), r"^plugins=", "plugins=(git z)", "plugins=(git z)")
    text = p.read_text()
    assert "plugins=(git z)" in text
    assert "plugins=(git)\n" not in text  # 旧值被替换
    assert 'ZSH_THEME="robbyrussell"' in text  # 无关行保留


def test_replace_or_append_dedup(tmp_path):
    p = tmp_path / "zshrc"
    p.write_text("plugins=(a)\nplugins=(b)\n")
    utils.replace_or_append(str(p), r"^plugins=", "plugins=(c)", "plugins=(c)")
    text = p.read_text()
    assert text.count("plugins=") == 1
    assert "plugins=(c)" in text


def test_replace_or_append_appends_when_no_match(tmp_path):
    p = tmp_path / "zshrc"
    p.write_text("export FOO=1\n")
    utils.replace_or_append(str(p), r"^ZSH_THEME=", 'ZSH_THEME="x"', 'ZSH_THEME="x"')
    assert 'ZSH_THEME="x"' in p.read_text()


def test_backup_write_creates_bak_once(tmp_path):
    p = tmp_path / "f"
    p.write_text("old")
    utils.backup_write(str(p), "new")
    assert p.read_text() == "new"
    assert (tmp_path / "f.bak").read_text() == "old"
    # 二次写入不覆盖已有 .bak
    utils.backup_write(str(p), "newer")
    assert (tmp_path / "f.bak").read_text() == "old"


def test_detect_arch_x86_64(monkeypatch):
    monkeypatch.setattr(utils.platform, "machine", lambda: "x86_64")
    assert utils.detect_arch() == "x86_64"


def test_detect_arch_aarch64(monkeypatch):
    monkeypatch.setattr(utils.platform, "machine", lambda: "aarch64")
    assert utils.detect_arch() == "arm64"


def test_real_home_uses_pwd_database(monkeypatch):
    import pwd

    monkeypatch.setenv("SUDO_USER", "nobody")
    assert utils.real_home() == pwd.getpwnam("nobody").pw_dir
