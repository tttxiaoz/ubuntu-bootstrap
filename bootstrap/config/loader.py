"""TOML 配置加载：示例兜底 + 用户覆盖合并 + 按任务 schema 校验。"""

from __future__ import annotations

import copy
import os
import shutil
from typing import Any

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - 开发机（<3.11）用 tomli 兜底
    import tomli as tomllib

from .schema import _get_path, _set_path


def load_config(path: str | None = None) -> Config:
    """加载并校验配置。

    1) 无 config.toml 则从 config.example.toml 复制生成并提示；
    2) tomllib 解析示例与用户配置，深合并（用户值优先）；
    3) 用全任务 Param 声明补齐默认值并校验；
    4) 返回不可变 Config。
    """
    base_dir = _base_dir()
    example_path = os.path.join(base_dir, "config.example.toml")
    cfg_path = path or os.path.join(base_dir, "config.toml")

    if not os.path.exists(cfg_path):
        shutil.copyfile(example_path, cfg_path)
        _chown_to_sudo_user(cfg_path)
        print(f"已生成默认配置 {cfg_path}（源自 config.example.toml），可按需修改后重跑。\n")

    base = _parse_toml(example_path)
    user = _parse_toml(cfg_path) if os.path.exists(cfg_path) else {}
    merged = _deep_merge(base, user)

    # 触发任务注册，随后用其 Param 声明补齐默认并校验
    from .. import tasks  # noqa: F401
    from ..core.task import Registry

    for param in Registry.all_params():
        value = _get_path(merged, param.key)
        if value is None:
            value = param.default
        _set_path(merged, param.key, param.validate(value, merged))

    return Config(merged)


class Config:
    """校验后的不可变配置视图。

    get("apt.mirror")  点路径读取
    cfg["apt"]         段读取
    as_dict()          整体字典快照
    """

    def __init__(self, data: dict) -> None:
        self._data = data

    def get(self, dotpath: str, default: Any = None) -> Any:
        value = _get_path(self._data, dotpath)
        return default if value is None else value

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def as_dict(self) -> dict:
        return copy.deepcopy(self._data)

    def __repr__(self) -> str:
        return f"Config({self._data!r})"


def _base_dir() -> str:
    # bootstrap/config/loader.py → 仓库根目录（config.example.toml 所在）
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _parse_toml(path: str) -> dict:
    with open(path, "rb") as fh:
        return tomllib.load(fh)


def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _chown_to_sudo_user(path: str) -> None:
    """把 root 生成的文件属主改回真实调用者（sudo 后默认属主是 root）。"""
    user = os.environ.get("SUDO_USER")
    if not user or user == "root":
        return
    try:
        shutil.chown(path, user=user)
    except (OSError, LookupError):
        pass
