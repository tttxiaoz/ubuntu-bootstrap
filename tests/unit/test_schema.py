"""config.schema.Param 候选解析与校验测试。"""

from __future__ import annotations

import pytest

from bootstrap.config.schema import Param


def test_resolve_choices_from_dict():
    p = Param("apt.mirror", "choice", choices="config:apt.mirrors")
    cfg = {"apt": {"mirrors": {"清华 TUNA": "u1", "阿里云": "u2"}}}
    assert p.resolve_choices(cfg) == ("清华 TUNA", "阿里云")


def test_resolve_choices_from_list():
    p = Param("system.timezone", "choice", choices="config:system.timezones")
    cfg = {"system": {"timezones": ["Asia/Shanghai", "UTC"]}}
    assert p.resolve_choices(cfg) == ("Asia/Shanghai", "UTC")


def test_resolve_choices_static():
    p = Param("nvim.method", "choice", choices=("apt", "github"))
    assert p.resolve_choices({}) == ("apt", "github")


def test_resolve_choices_missing_returns_empty():
    p = Param("x", "choice", choices="config:not.defined")
    assert p.resolve_choices({}) == ()


def test_validate_bool_true():
    p = Param("ssh.password_auth", "bool", default=True)
    assert p.validate(True, {}) is True
    assert p.validate("yes", {}) is True
    assert p.validate("false", {}) is False


def test_validate_bool_bad_raises():
    p = Param("k", "bool")
    with pytest.raises(ValueError):
        p.validate("maybe", {})


def test_validate_choice_out_of_range_raises():
    p = Param("zsh.theme", "choice", choices=("default", "random"))
    with pytest.raises(ValueError):
        p.validate("powerlevel10k", {})


def test_validate_multi_not_list_raises():
    p = Param("base_tools.selected", "multi")
    with pytest.raises(ValueError):
        p.validate("git", {})
