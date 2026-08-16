"""任务注册表：有序列表，入口与 runner 据此生成菜单与执行。"""

from __future__ import annotations

from .apt_mirror import AptMirrorTask
from .locale_timezone import LocaleTimezoneTask
from .system_update import SystemUpdateTask
from .base_tools import BaseToolsTask
from .nvim import NvimTask
from .fzf import FzfTask
from .zsh import ZshTask
from .ssh import SshTask

# 顺序即菜单显示顺序；depends_on 决定执行顺序
REGISTRY: list = [
    AptMirrorTask(),
    LocaleTimezoneTask(),
    SystemUpdateTask(),
    BaseToolsTask(),
    NvimTask(),
    FzfTask(),
    ZshTask(),
    SshTask(),
]

TASKS = {t.id: t for t in REGISTRY}
