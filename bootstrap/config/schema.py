"""配置参数声明（Param）与路径/类型辅助函数。

Param 是重写的核心概念：任务显式声明自己需要的配置项，向导、批量执行、
校验、--list 展示、文档都从 Param 列表驱动。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ParamType = Literal["str", "bool", "choice", "multi", "password"]


@dataclass(frozen=True)
class Param:
    """一个配置参数声明。

    key           TOML 点路径，如 "apt.mirror"；与任务读取时同键。
    type          "str" | "bool" | "choice" | "multi" | "password"
    default       内置默认值（config.toml 缺失时的兜底）
    choices       静态候选 tuple，或 "config:apt.mirrors" 引用配置目录
    label         向导显示名
    help          向导/文档说明
    interactive   False 时向导跳过该项、直接用 config 值
    """

    key: str
    type: ParamType
    default: Any = None
    choices: tuple[str, ...] | str | None = None
    label: str = ""
    help: str = ""
    interactive: bool = True

    def resolve_choices(self, config: dict) -> tuple[str, ...]:
        """解析候选列表；"config:path" 引用配置中的目录表/数组。"""
        if isinstance(self.choices, str) and self.choices.startswith("config:"):
            val = _get_path(config, self.choices[len("config:"):])
            if isinstance(val, dict):
                return tuple(val.keys())
            if isinstance(val, (list, tuple)):
                return tuple(val)
            return ()
        return tuple(self.choices) if self.choices else ()

    def validate(self, value: Any, config: dict) -> Any:
        """校验并规范化，返回内部值；非法抛 ValueError。"""
        if self.type == "bool":
            return _to_bool(value, self.key)
        if self.type == "choice":
            opts = self.resolve_choices(config)
            if opts and value not in opts:
                raise ValueError(
                    f"配置键 {self.key} 的取值 {value!r} 不在候选 {list(opts)!r} 中")
            return value
        if self.type == "multi":
            if not isinstance(value, list):
                raise ValueError(f"配置键 {self.key} 应为数组")
            return [str(v) for v in value]
        if self.type == "password":
            return "" if value is None else str(value)
        # str
        return str(value)


def _to_bool(value: Any, key: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        low = value.strip().lower()
        if low in ("yes", "true", "1", "on"):
            return True
        if low in ("no", "false", "0", "off"):
            return False
    raise ValueError(f"配置键 {key} 应为布尔值，得到 {value!r}")


def _get_path(config: dict, dotpath: str) -> Any:
    """按点路径读取嵌套字典；缺失返回 None。"""
    cur: Any = config
    for part in dotpath.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _set_path(config: dict, dotpath: str, value: Any) -> None:
    """按点路径写入嵌套字典（中间层自动创建）。"""
    parts = dotpath.split(".")
    cur = config
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value
