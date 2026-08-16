"""任务基类、@task 装饰器与注册表。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..config.schema import Param
from ..platform import sys as psys


@dataclass(frozen=True)
class CheckResult:
    """check() 的返回：是否已配置 + 状态说明。"""

    done: bool
    note: str = ""


@dataclass(frozen=True)
class TaskMeta:
    id: str
    name: str
    description: str
    depends_on: tuple[str, ...]
    params: tuple[Param, ...]


class Context:
    """任务执行上下文：配置 + 日志 + apt 工具 + 执行选项。"""

    def __init__(self, config, log, apt, *, force: bool = False) -> None:
        self.config = config
        self.log = log
        self.apt = apt
        self.force = force

    def run_cmd(self, cmd: list[str], **kw):
        """执行命令并自动接入日志（命令行 + 子进程输出 tee）。"""
        if self.log is not None:
            kw.setdefault("log", self.log.log)
            kw.setdefault("tee", self.log.stream)
        return psys.run_cmd(cmd, **kw)


class Task(ABC):
    """一个可执行的初始化任务。

    check(): 返回 CheckResult，用于菜单状态显示与幂等跳过。
    run():   实际执行，失败抛 platform.TaskError。
    """

    meta: TaskMeta = TaskMeta("", "", "", (), ())

    @abstractmethod
    def check(self, ctx: Context) -> CheckResult:
        raise NotImplementedError

    @abstractmethod
    def run(self, ctx: Context) -> None:
        raise NotImplementedError


def task(*, id: str, name: str, description: str = "",
         depends_on: tuple[str, ...] = (), params: tuple[Param, ...] = ()):
    """类装饰器：注入 TaskMeta 并注册进 Registry。"""

    def decorate(cls):
        cls.meta = TaskMeta(id=id, name=name, description=description,
                            depends_on=depends_on, params=params)
        Registry.register(cls)
        return cls

    return decorate


class Registry:
    """任务注册表：按导入顺序收集所有任务。"""

    _classes: list[type[Task]] = []
    _by_id: dict[str, type[Task]] = {}

    @classmethod
    def register(cls, task_cls: type[Task]) -> None:
        if task_cls.meta.id in cls._by_id:
            raise ValueError(f"任务 id 重复: {task_cls.meta.id}")
        cls._classes.append(task_cls)
        cls._by_id[task_cls.meta.id] = task_cls

    @classmethod
    def all(cls) -> list[Task]:
        return [c() for c in cls._classes]

    @classmethod
    def get(cls, task_id: str) -> Task:
        return cls._by_id[task_id]()

    @classmethod
    def ids(cls) -> list[str]:
        return [c.meta.id for c in cls._classes]

    @classmethod
    def all_params(cls) -> list[Param]:
        return [p for c in cls._classes for p in c.meta.params]
