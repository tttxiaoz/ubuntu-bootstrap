"""apt_mirror 纯函数与文件改写测试。"""

from __future__ import annotations

from types import SimpleNamespace

from lib.tasks import apt_mirror as apt


def _cfg(mirror="清华 TUNA"):
    return SimpleNamespace(
        APT_MIRROR=mirror,
        APT_MIRRORS={
            "清华 TUNA": "https://mirrors.tuna.tsinghua.edu.cn/ubuntu/",
            "阿里云": "https://mirrors.aliyun.com/ubuntu/",
        },
    )


def test_rewrite_deb_uri_archive():
    line = "deb http://archive.ubuntu.com/ubuntu jammy main restricted"
    out = apt._rewrite_deb_uri(line, "https://mirrors.tuna.tsinghua.edu.cn/ubuntu")
    assert out == "deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu jammy main restricted"


def test_rewrite_deb_uri_security():
    line = "deb http://security.ubuntu.com/ubuntu jammy-security main"
    out = apt._rewrite_deb_uri(line, "https://mirrors.tuna.tsinghua.edu.cn/ubuntu")
    assert out == "deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu jammy-security main"


def test_rewrite_deb_uri_https():
    line = "deb https://archive.ubuntu.com/ubuntu jammy main"
    out = apt._rewrite_deb_uri(line, "https://mirrors.aliyun.com/ubuntu")
    assert out == "deb https://mirrors.aliyun.com/ubuntu jammy main"


def test_rewrite_deb_uri_unrelated_line_unchanged():
    line = "# deb http://archive.ubuntu.com/ubuntu jammy main"
    assert apt._rewrite_deb_uri(line, "https://mirror") == line


def test_default_deb822_uses_mirror_for_security():
    out = apt._default_deb822("noble", "https://mirrors.tuna.tsinghua.edu.cn/ubuntu")
    assert "URIs: https://mirrors.tuna.tsinghua.edu.cn/ubuntu" in out
    assert "security.ubuntu.com" not in out
    assert "noble-security" in out


def test_has_mirror_true(tmp_path, monkeypatch):
    lst = tmp_path / "sources.list"
    lst.write_text("deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu jammy main\n")
    monkeypatch.setattr(apt, "_SOURCES_LIST", str(lst))
    monkeypatch.setattr(apt, "_SOURCES_DEB822", str(tmp_path / "missing.sources"))
    assert apt._has_mirror(_cfg()) is True


def test_has_mirror_false(tmp_path, monkeypatch):
    lst = tmp_path / "sources.list"
    lst.write_text("deb http://archive.ubuntu.com/ubuntu jammy main\n")
    monkeypatch.setattr(apt, "_SOURCES_LIST", str(lst))
    monkeypatch.setattr(apt, "_SOURCES_DEB822", str(tmp_path / "missing.sources"))
    assert apt._has_mirror(_cfg()) is False


def test_patch_classic_rewrites_archive_and_security(tmp_path, monkeypatch):
    lst = tmp_path / "sources.list"
    lst.write_text(
        "deb http://archive.ubuntu.com/ubuntu jammy main restricted\n"
        "deb http://security.ubuntu.com/ubuntu jammy-security main\n"
        "# comment\n"
    )
    monkeypatch.setattr(apt, "_SOURCES_LIST", str(lst))
    task = apt.AptMirrorTask()
    task._patch_classic("jammy", "https://mirrors.tuna.tsinghua.edu.cn/ubuntu")
    text = lst.read_text()
    assert "http://archive.ubuntu.com" not in text
    assert "http://security.ubuntu.com" not in text
    assert "https://mirrors.tuna.tsinghua.edu.cn/ubuntu jammy main" in text
    assert "https://mirrors.tuna.tsinghua.edu.cn/ubuntu jammy-security main" in text
    assert "# comment" in text
