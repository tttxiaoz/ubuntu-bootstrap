"""platform.sys 系统探测测试。"""

from __future__ import annotations

from bootstrap.platform import sys as psys


def test_detect_arch_x86_64(monkeypatch):
    monkeypatch.setattr(psys.platform, "machine", lambda: "x86_64")
    assert psys.detect_arch() == "x86_64"


def test_detect_arch_aarch64(monkeypatch):
    monkeypatch.setattr(psys.platform, "machine", lambda: "aarch64")
    assert psys.detect_arch() == "arm64"
