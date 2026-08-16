"""zsh 任务的 .zshrc 读写与插件安装纯逻辑测试。"""

from __future__ import annotations

import os

from bootstrap.config import Config
from bootstrap.platform import TaskError
from bootstrap.tasks.zsh import ZshTask


def _cfg(plugins=None, theme="default"):
    return Config({"zsh": {"plugins": plugins or ["git"], "theme": theme}})


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


def test_write_zshrc_default_theme(tmp_path, make_ctx):
    ctx = make_ctx({"zsh": {"plugins": ["git"], "theme": "default"}})
    ZshTask()._write_zshrc(ctx, str(tmp_path))
    text = (tmp_path / ".zshrc").read_text()
    assert "plugins=(git)" in text
    assert 'ZSH_THEME="robbyrussell"' in text


def test_write_zshrc_powerlevel10k(tmp_path, make_ctx):
    ctx = make_ctx({"zsh": {"plugins": ["git"], "theme": "powerlevel10k"}})
    ZshTask()._write_zshrc(ctx, str(tmp_path))
    text = (tmp_path / ".zshrc").read_text()
    assert 'ZSH_THEME="powerlevel10k/powerlevel10k"' in text
    assert "POWERLEVEL9K_DISABLE_CONFIGURATION_WIZARD=true" in text


def test_install_plugin_apt_creates_symlink(tmp_path, monkeypatch, make_ctx):
    src = tmp_path / "real.zsh"
    src.write_text("# plugin")
    dest = tmp_path / "custom" / "zsh-syntax-highlighting"

    monkeypatch.setattr(ZshTask, "_find_plugin_script",
                        staticmethod(lambda pkg, name: str(src)))

    ok = ZshTask()._install_plugin_apt(make_ctx(), "zsh-syntax-highlighting",
                                       "zsh-syntax-highlighting", str(dest))
    assert ok is True
    target = dest / "zsh-syntax-highlighting.plugin.zsh"
    assert target.is_symlink()
    assert os.readlink(str(target)) == str(src)


def test_install_plugin_apt_fails_on_apt_error(monkeypatch, make_ctx):
    class BoomApt:
        def install(self, packages, **kw):
            raise TaskError("apt failed")

    ok = ZshTask()._install_plugin_apt(make_ctx(apt=BoomApt()), "pkg", "name",
                                       "/tmp/nonexistent")
    assert ok is False


def test_install_plugin_apt_fails_when_no_script(monkeypatch, make_ctx):
    monkeypatch.setattr(ZshTask, "_find_plugin_script", staticmethod(lambda pkg, name: None))
    ok = ZshTask()._install_plugin_apt(make_ctx(), "pkg", "name", "/tmp/nonexistent")
    assert ok is False


def test_install_external_plugins_apt_only(tmp_path, monkeypatch, make_ctx):
    """外部插件一律走 apt 安装并 symlink，不再 clone GitHub。"""
    calls = []
    monkeypatch.setattr(ZshTask, "_install_plugin_apt",
                        lambda self, ctx, pkg, name, dest: calls.append(("apt", pkg, name)) or True)

    ctx = make_ctx({"zsh": {"external_plugins_apt": {
        "zsh-autosuggestions": "zsh-autosuggestions",
        "zsh-syntax-highlighting": "zsh-syntax-highlighting",
    }}})
    ZshTask()._install_external_plugins(ctx, str(tmp_path))
    assert ("apt", "zsh-autosuggestions", "zsh-autosuggestions") in calls
    assert ("apt", "zsh-syntax-highlighting", "zsh-syntax-highlighting") in calls


def test_install_external_plugins_logs_warning_on_failure(tmp_path, monkeypatch, make_ctx):
    monkeypatch.setattr(ZshTask, "_install_plugin_apt",
                        lambda self, ctx, pkg, name, dest: False)
    ctx = make_ctx({"zsh": {"external_plugins_apt": {"zsh-autosuggestions": "pkg"}}})
    ZshTask()._install_external_plugins(ctx, str(tmp_path))
    assert any("zsh-autosuggestions" in m and "失败" in m for m in ctx.log.messages)
