"""真实用户识别：SUDO_USER 优先，回退 pwd 数据库。"""

from __future__ import annotations

import os


def real_user() -> str:
    """识别真实登录用户（sudo 时为 SUDO_USER），无则回退 root。"""
    return os.environ.get("SUDO_USER") or os.environ.get("USER") or "root"


def real_home() -> str:
    """真实用户的家目录（优先用 pwd 数据库，回退 HOME）。"""
    user = real_user()
    try:
        import pwd

        return pwd.getpwnam(user).pw_dir
    except (ImportError, KeyError):
        if user == "root":
            return "/root"
        return os.path.expanduser(f"~{user}")
