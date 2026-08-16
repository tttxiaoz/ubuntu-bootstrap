"""tui 的降级分支测试（不依赖 rich/questionary 是否安装，强制走纯文本路径）。"""

from __future__ import annotations

from types import SimpleNamespace

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
