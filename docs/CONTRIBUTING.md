# 贡献指南

## 环境准备

目标运行时 **Ubuntu 24.04+ / Python 3.11+**（零运行时依赖）。开发机建议 Python 3.11+，`<3.11` 会经 `tomli` 回退解析 TOML（仅开发依赖）。

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'      # pytest + ruff（+ tomli 回退）
```

## 运行测试

```bash
pytest                      # 单元测试 + 集成测试（需 Docker）
pytest tests/unit           # 仅单元测试
pytest tests/integration    # 仅 Docker 集成测试（需 Docker 守护进程）
ruff check .                # 静态检查
```

集成测试会在真实 `ubuntu:24.04` 容器里验证启动、dry-run 与任务幂等。

## 目录职责

| 目录 | 职责 |
|---|---|
| `bootstrap/config/` | `Param` 声明（schema）与 TOML 加载校验（loader） |
| `bootstrap/core/` | `Task`/`@task` 注册、`Plan`、`Runner`、`Logger` |
| `bootstrap/platform/` | 无业务逻辑的工具层：sys / apt / fs / user |
| `bootstrap/ui/` | ANSI、终端原语、向导（只产出 Plan，不执行） |
| `bootstrap/tasks/` | 各初始化任务 |

## 新增一个任务

1. 在 `bootstrap/tasks/` 新建 `my_task.py`：

```python
"""任务描述。"""

from ..config.schema import Param
from ..core.task import CheckResult, Context, Task, task
from ..platform import sys as psys


@task(
    id="my_task",
    name="任务显示名",
    description="任务说明（向导展示）",
    depends_on=("apt_mirror",),            # 依赖的任务 id，决定执行顺序
    params=[                               # 本任务的配置契约（驱动向导/校验/--list）
        Param("my_task.mode", "choice", default="fast",
              choices=("fast", "safe"), label="运行模式"),
    ],
)
class MyTask(Task):
    def check(self, ctx: Context) -> CheckResult:
        # 幂等判断：已配置返回 CheckResult(True, "说明")，未配置返回 (False, "说明")
        return CheckResult(False, "未配置")

    def run(self, ctx: Context) -> None:
        # 读配置：ctx.config.get("my_task.mode")
        # 执行命令：ctx.run_cmd(["cmd", "arg"]) 或 ctx.apt.install(["pkg"])
        # 写日志：ctx.log.log("消息", style="green")；子进程输出经 ctx.run_cmd 自动 tee
        # 失败抛 psys.TaskError("原因")
        pass
```

2. 在 `bootstrap/tasks/__init__.py` 的 `from . import (...)` 列表中加入 `my_task`（**顺序即菜单顺序，勿用 isort 重排**）。
3. 若引入新配置键，在 `config.example.toml` 增加对应分节，并让 `Param.key` 指向它（如 `my_task.mode`）。
4. 在 `tests/unit/` 补充 `check`/`run` 的纯逻辑单测；涉及真实系统行为的在 `tests/integration/` 补 Docker 测试。

## 约定

- **幂等**：`check` 必须只读探测、无副作用；已配置的任务会被自动跳过。
- **能用 apt 就 apt**：优先 `ctx.apt.install`，仅 apt 没有的才从 GitHub 获取。
- **写系统文件前备份**：用 `platform.fs.backup_write`（自动生成 `*.bak`）。
- **配置读写**：任务只读 `ctx.config`，绝不写回；运行时答案由向导经 `Plan.answers` 覆盖。
- **代码风格**：`ruff check .`（line-length 100），`py311` 目标。

## 配置键约定

- 键用点路径分节（`apt.mirror`、`zsh.theme`），与 `Param.key` 一致。
- 候选目录（如 `apt.mirrors`）放配置里供 `choices="config:..."` 引用，便于用户扩展。
- 布尔用 TOML 真布尔（`password_auth = true`），写入系统时再转 `yes/no`。
