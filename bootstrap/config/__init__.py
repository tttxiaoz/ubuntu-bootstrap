"""配置系统：Param 声明、TOML 加载与校验。"""

from .loader import Config, load_config
from .schema import Param

__all__ = ["Config", "Param", "load_config"]
