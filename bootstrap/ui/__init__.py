"""表现层：ANSI 着色、终端原语、向导（只产出 Plan，不执行）。"""

from .wizard import build_plan

__all__ = ["build_plan"]
