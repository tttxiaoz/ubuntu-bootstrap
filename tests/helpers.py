"""测试辅助：加载 config.example.py 为命名空间模块，便于构造 cfg。"""

from __future__ import annotations

import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_example_config():
    """返回加载好的 config.example.py 模块对象（属性为常量）。"""
    path = os.path.join(ROOT, "config.example.py")
    spec = importlib.util.spec_from_file_location("_test_cfg_example", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
