"""config.loader 的合并与校验逻辑测试。"""

from __future__ import annotations

import os

from bootstrap.config.loader import _deep_merge, _parse_toml


def test_deep_merge_nested():
    base = {"apt": {"mirror": "清华 TUNA", "mirrors": {"a": ""}}}
    override = {"apt": {"mirror": "阿里云"}}
    merged = _deep_merge(base, override)
    assert merged["apt"]["mirror"] == "阿里云"
    assert merged["apt"]["mirrors"]["a"] == ""  # 未覆盖的嵌套键保留


def test_deep_merge_scalar_replace():
    assert _deep_merge({"a": [1, 2]}, {"a": [3]}) == {"a": [3]}


def test_parse_toml(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('[apt]\nmirror = "清华 TUNA"\n\n[ssh]\npassword_auth = true\n')
    data = _parse_toml(str(p))
    assert data["apt"]["mirror"] == "清华 TUNA"
    assert data["ssh"]["password_auth"] is True


def test_load_config_generates_and_validates(tmp_path, monkeypatch):
    """从示例生成 config.toml 并解析校验。"""
    import bootstrap.config.loader as loader

    monkeypatch.setattr(loader, "_base_dir", lambda: str(tmp_path))
    # 复制示例到 tmp 下
    import shutil

    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    example = os.path.join(repo_root, "config.example.toml")
    shutil.copyfile(example, os.path.join(str(tmp_path), "config.example.toml"))

    import bootstrap.tasks  # noqa: F401  触发注册

    cfg = loader.load_config()
    assert cfg.get("apt.mirror") == "清华 TUNA"
    assert cfg.get("ssh.password_auth") is True
    assert os.path.exists(os.path.join(str(tmp_path), "config.toml"))
