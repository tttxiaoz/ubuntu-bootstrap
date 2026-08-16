"""zsh 任务的 .zshrc 读写纯逻辑测试。"""

from __future__ import annotations

from types import SimpleNamespace

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
