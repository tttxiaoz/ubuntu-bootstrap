"""任务模块：导入即触发 @task 自动注册，顺序即菜单显示顺序。

注意：此处顺序有语义（菜单/向导展示顺序），勿用 isort 重排。
"""

# isort: off
from . import (  # noqa: F401
    apt_mirror,
    system_update,
    set_password,
    ssh,
    locale_timezone,
    base_tools,
    fzf,
    nvim,
    zsh,
)
# isort: on
