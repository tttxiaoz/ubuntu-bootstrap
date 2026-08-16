"""ui.questions_for_task / resolve_options 测试。"""

from __future__ import annotations

from types import SimpleNamespace

from lib import ui


def test_questions_for_task_filters_interactive():
    cfg = SimpleNamespace(QUESTIONS=[
        {"id": "a", "task": "zsh", "interactive": True},
        {"id": "b", "task": "zsh", "interactive": False},
        {"id": "c", "task": "ssh", "interactive": True},
    ])
    qs = ui.questions_for_task(cfg, "zsh")
    assert [q["id"] for q in qs] == ["a"]


def test_questions_for_task_missing_key_defaults_interactive():
    cfg = SimpleNamespace(QUESTIONS=[{"id": "a", "task": "zsh"}])
    assert len(ui.questions_for_task(cfg, "zsh")) == 1


def test_resolve_options_from_dict():
    cfg = SimpleNamespace(APT_MIRRORS={"清华 TUNA": "u1", "阿里云": "u2"})
    assert ui.resolve_options(cfg, {"options": "@APT_MIRRORS"}) == ["清华 TUNA", "阿里云"]


def test_resolve_options_from_list():
    cfg = SimpleNamespace(TIMEZONES=["Asia/Shanghai", "UTC"])
    assert ui.resolve_options(cfg, {"options": "@TIMEZONES"}) == ["Asia/Shanghai", "UTC"]


def test_resolve_options_static_list():
    cfg = SimpleNamespace()
    assert ui.resolve_options(cfg, {"options": ["a", "b"]}) == ["a", "b"]


def test_resolve_options_missing_var_returns_empty():
    cfg = SimpleNamespace()
    assert ui.resolve_options(cfg, {"options": "@NOT_DEFINED"}) == []
