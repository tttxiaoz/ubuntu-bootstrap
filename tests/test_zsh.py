"""zsh 任务的 .zshrc 读写与插件安装纯逻辑测试。"""

from __future__ import annotations

import os
from types import SimpleNamespace

from lib import utils
from lib.tasks.zsh import ZshTask


def _cfg(plugins=None, theme="default"):
    return SimpleNamespace(
        ZSH_PLUGINS=plugins or ["git"],
        ZSH_THEME=theme,
    )


def test_zshrc_matches_random(tmp_path):
    cfg = _cfg(plugins=["git", "z"], theme="random")
    (tmp_path / ".zshrc").write_text('plugins=(git z)\nZSH_THEME="random"\n')
    assert ZshTask()._zshrc_matches(cfg, str(tmp_path)) is True


def test_zshrc_mismatch_plugins(tmp_path):
    cfg = _cfg(plugins=["git", "z"], theme="random")
    (tmp_path / ".zshrc").write_text('plugins=(git)\nZSH_THEME="random"\n')
    assert ZshTask()._zshrc_matches(cfg, str(tmp_path)) is False


def test_zshrc_mismatch_theme(tmp_path):
    cfg = _cfg(plugins=["git"], theme="random")
    (tmp_path / ".zshrc").write_text('plugins=(git)\nZSH_THEME="robbyrussell"\n')
    assert ZshTask()._zshrc_matches(cfg, str(tmp_path)) is False


def test_write_zshrc_default_theme(tmp_path):
    cfg = _cfg(plugins=["git"], theme="default")
    ZshTask()._write_zshrc(cfg, str(tmp_path), "default", log=None)
    text = (tmp_path / ".zshrc").read_text()
    assert "plugins=(git)" in text
    assert 'ZSH_THEME="robbyrussell"' in text


def test_write_zshrc_powerlevel10k(tmp_path):
    cfg = _cfg(plugins=["git"], theme="powerlevel10k")
    ZshTask()._write_zshrc(cfg, str(tmp_path), "powerlevel10k", log=None)
    text = (tmp_path / ".zshrc").read_text()
    assert 'ZSH_THEME="powerlevel10k/powerlevel10k"' in text
    assert "POWERLEVEL9K_DISABLE_CONFIGURATION_WIZARD=true" in text


def test_install_plugin_apt_creates_symlink(tmp_path, monkeypatch):
    src = tmp_path / "real.zsh"
    src.write_text("# plugin")
    dest = tmp_path / "custom" / "zsh-syntax-highlighting"

    monkeypatch.setattr(utils, "apt_install", lambda *a, **k: None)
    monkeypatch.setattr(ZshTask, "_find_plugin_script",
                        staticmethod(lambda pkg, name: str(src)))

    ok = ZshTask()._install_plugin_apt("zsh-syntax-highlighting",
                                       "zsh-syntax-highlighting", str(dest), log=None)
    assert ok is True
    target = dest / "zsh-syntax-highlighting.plugin.zsh"
    assert target.is_symlink()
    assert os.readlink(str(target)) == str(src)


def test_install_plugin_apt_fails_on_apt_error(monkeypatch):
    def boom(*a, **k):
        raise utils.TaskError("apt failed")

    monkeypatch.setattr(utils, "apt_install", boom)
    ok = ZshTask()._install_plugin_apt("pkg", "name", "/tmp/nonexistent", log=None)
    assert ok is False


def test_install_plugin_apt_fails_when_no_script(monkeypatch):
    monkeypatch.setattr(utils, "apt_install", lambda *a, **k: None)
    monkeypatch.setattr(ZshTask, "_find_plugin_script", staticmethod(lambda pkg, name: None))
    ok = ZshTask()._install_plugin_apt("pkg", "name", "/tmp/nonexistent", log=None)
    assert ok is False


def test_install_external_plugins_prefer_apt(tmp_path, monkeypatch):
    """apt 有包时优先 apt 安装，不调用 git clone。"""
    calls = []
    monkeypatch.setattr(utils, "apt_install", lambda pkgs, **k: calls.append(("apt", pkgs)))
    monkeypatch.setattr(ZshTask, "_install_plugin_apt",
                        lambda self, pkg, name, dest, log: calls.append(("symlink", name)) or True)

    cfg = SimpleNamespace(
        ZSH_EXTERNAL_PLUGINS={"zsh-autosuggestions": "https://github.com/x"},
        ZSH_EXTERNAL_PLUGINS_APT={"zsh-autosuggestions": "zsh-autosuggestions"},
    )
    ZshTask()._install_external_plugins(cfg, str(tmp_path), log=None)
    assert ("symlink", "zsh-autosuggestions") in calls
    assert not any(c[0] == "clone" for c in calls)
