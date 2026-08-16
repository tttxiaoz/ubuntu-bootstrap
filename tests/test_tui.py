"""tui 的降级分支测试（不依赖 rich/questionary 是否安装，强制走纯文本路径）。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from lib import tui


def _cfg():
    return SimpleNamespace(
        PIP_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple",
        TUI_PACKAGES=["rich", "questionary"],
    )


def test_paint_applies_ansi():
    out = tui._paint("x", "red", "bold")
    assert out.startswith("\033[")
    assert out.endswith("\033[0m")
    assert "x" in out


def test_packages_default():
    assert tui._packages(SimpleNamespace()) == ["rich", "questionary"]


def test_packages_from_cfg():
    assert tui._packages(SimpleNamespace(TUI_PACKAGES=["rich"])) == ["rich"]


def test_index_url():
    assert tui._index_url(_cfg()) == "https://pypi.tuna.tsinghua.edu.cn/simple"


def test_choose_fallback_selects_by_number(monkeypatch):
    monkeypatch.setattr(tui, "questionary_available", lambda: False)
    monkeypatch.setattr("builtins.input", lambda *a, **k: "2")
    assert tui.choose(["a", "b", "c"], header="h", selected="a") == "b"


def test_choose_fallback_default_on_enter(monkeypatch):
    monkeypatch.setattr(tui, "questionary_available", lambda: False)
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")
    assert tui.choose(["a", "b"], selected="b") == "b"


def test_choose_fallback_empty_options():
    assert tui.choose([], header="h") is None


def test_confirm_fallback_default(monkeypatch):
    monkeypatch.setattr(tui, "questionary_available", lambda: False)
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")
    assert tui.confirm("q?", default=True) is True
    assert tui.confirm("q?", default=False) is False


def test_confirm_fallback_yes(monkeypatch):
    monkeypatch.setattr(tui, "questionary_available", lambda: False)
    monkeypatch.setattr("builtins.input", lambda *a, **k: "y")
    assert tui.confirm("q?", default=False) is True


def test_print_summary_table_fallback(monkeypatch, capsys):
    monkeypatch.setattr(tui, "rich_available", lambda: False)
    tui.print_summary_table([("zsh", "✅"), ("nvim", "❌")])
    out = capsys.readouterr().out
    assert "zsh" in out and "nvim" in out


def test_multiselect_fallback_all_on_enter(monkeypatch):
    monkeypatch.setattr(tui, "questionary_available", lambda: False)
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")
    assert tui.multiselect(["a", "b", "c"], header="h") == ["a", "b", "c"]


def test_multiselect_fallback_subset(monkeypatch):
    monkeypatch.setattr(tui, "questionary_available", lambda: False)
    monkeypatch.setattr("builtins.input", lambda *a, **k: "1,3")
    assert tui.multiselect(["a", "b", "c"]) == ["a", "c"]


def test_multiselect_fallback_empty_options():
    assert tui.multiselect([]) == []


def test_password_fallback_match(monkeypatch):
    import getpass

    monkeypatch.setattr(tui, "questionary_available", lambda: False)
    monkeypatch.setattr(getpass, "getpass", lambda *a, **k: "pw123")
    assert tui.password("密码") == "pw123"


def test_password_fallback_mismatch(monkeypatch):
    import getpass

    monkeypatch.setattr(tui, "questionary_available", lambda: False)
    it = iter(["pw1", "pw2"])
    monkeypatch.setattr(getpass, "getpass", lambda *a, **k: next(it))
    assert tui.password("密码") is None


def test_multiselect_questionary_uses_checked(monkeypatch):
    """questionary.checkbox 的 default 只接受单值，预设多项必须用 Choice(checked=True)。"""
    import sys

    captured = {}

    class FakeChoice:
        def __init__(self, title, checked=False):
            captured["choices"].append((title, checked))

    class FakePrompt:
        def ask(self):
            return ["git", "curl"]

    def fake_checkbox(message, choices, **kwargs):
        captured["message"] = message
        captured["n_choices"] = len(choices)
        captured["kwargs"] = kwargs
        return FakePrompt()

    fake_mod = SimpleNamespace(Choice=FakeChoice, checkbox=fake_checkbox)
    monkeypatch.setattr(tui, "questionary_available", lambda: True)
    monkeypatch.setitem(sys.modules, "questionary", fake_mod)

    captured["choices"] = []
    result = tui.multiselect(["git", "curl", "htop"], selected=["git", "curl"])

    assert result == ["git", "curl"]
    assert [c[0] for c in captured["choices"]] == ["git", "curl", "htop"]
    assert [c[1] for c in captured["choices"]] == [True, True, False]
    assert "default" not in captured["kwargs"]


def _patch_questionary_interrupt(monkeypatch, attrs):
    """注入会抛 KeyboardInterrupt 的假 questionary 模块，返回它的 attrs。"""
    import sys

    class FakePrompt:
        def ask(self):
            raise KeyboardInterrupt

    fake_mod = SimpleNamespace(**{k: (lambda *a, **k: FakePrompt()) for k in attrs})
    monkeypatch.setattr(tui, "questionary_available", lambda: True)
    monkeypatch.setitem(sys.modules, "questionary", fake_mod)
    return fake_mod


def test_choose_propagates_keyboard_interrupt(monkeypatch):
    _patch_questionary_interrupt(monkeypatch, ["select"])
    with pytest.raises(KeyboardInterrupt):
        tui.choose(["a", "b"])


def test_confirm_propagates_keyboard_interrupt(monkeypatch):
    _patch_questionary_interrupt(monkeypatch, ["confirm"])
    with pytest.raises(KeyboardInterrupt):
        tui.confirm("q?")


def test_multiselect_propagates_keyboard_interrupt(monkeypatch):
    import sys

    class FakePrompt:
        def ask(self):
            raise KeyboardInterrupt

    fake_mod = SimpleNamespace(
        Choice=lambda *a, **k: None,
        checkbox=lambda *a, **k: FakePrompt(),
    )
    monkeypatch.setattr(tui, "questionary_available", lambda: True)
    monkeypatch.setitem(sys.modules, "questionary", fake_mod)
    with pytest.raises(KeyboardInterrupt):
        tui.multiselect(["a", "b"])


def test_password_propagates_keyboard_interrupt(monkeypatch):
    _patch_questionary_interrupt(monkeypatch, ["password"])
    with pytest.raises(KeyboardInterrupt):
        tui.password("密码")
