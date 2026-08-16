"""任务基类：定义统一接口（id/name/description/depends_on/check/run）。"""

from __future__ import annotations


class Task:
    """一个可执行的初始化任务。

    - check(): 返回 (是否已配置, 状态说明文本)，用于菜单状态显示与幂等跳过。
    - run():   实际执行，失败抛 utils.TaskError。
    """

    id: str = ""
    name: str = ""
    description: str = ""
    depends_on: list[str] = []

    def check(self, cfg, log=None) -> tuple[bool, str]:
        """默认未配置。子类覆盖以实现幂等判断。"""
        return False, "未配置"

    def run(self, cfg, log=None) -> None:
        raise NotImplementedError
