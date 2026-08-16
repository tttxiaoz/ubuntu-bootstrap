# Ubuntu Bootstrap 重构设计文档

> 状态：一期~三期已落地（配置系统 / core 执行引擎 / 任务迁移 / 单元测试），四期 Docker 集成测试与五期收尾待做。
> 目标：在保留现有「幂等任务 + 可降级向导」设计哲学的前提下，做一次架构级重写。

---

## 1. 背景与目标

当前实现（`init.py` + `lib/`）已经能用、且结构不差，但存在几处结构性问题：

1. **配置系统混杂**：`config.example.py` 可执行模块 + `QUESTIONS` 全局列表 + `load_config` 里的 backfill 逻辑，三套机制混在一起，配置契约不清晰。
2. **UI 与执行耦合**：`ui.py` 的 `_tui_run` / `_plain_run` 两套向导 + `init.py` 的批量确认，三处重复「确认任务 → 问配置 → 执行」流程，只因为「选什么」和「怎么执行」没分开。
3. **任务注册手写**：`REGISTRY` 列表手写，加任务要改 `__init__.py`。
4. **日志不完整**：子进程实际输出不进 `logs/`（只记了命令行的 `$ cmd`）。
5. **工具层单文件**：`utils.py` 把命令执行 / os 检测 / apt / 备份 / 用户识别全塞一起。

### 重写目标（非目标）

| 目标 | 说明 |
|---|---|
| 配置契约显式化 | 每个任务声明自己的参数（类型/候选/默认/交互），向导、批量、校验、文档都由这份声明驱动 |
| 执行与表现分离 | 抽象 `Plan` 模型，UI 只负责产出 Plan，执行完全复用单一 `Runner` |
| 插件化注册 | `@task` 装饰器自动收集任务 |
| 日志可追踪 | 子进程输出 tee 进日志 + `--verbose` + JSON 结果导出 |
| 测试分层 | 单元测试 + Docker 集成测试 |

### 已锁定的决策

| 决策 | 结论 | 理由 |
|---|---|---|
| 重构力度 | 架构级重写 | 用户拍板 |
| 配置格式 | TOML | 用户拍板 |
| 最低 Ubuntu | **24.04+（Python 3.12+）** | 放弃 22.04，stdlib 自带 `tomllib`，无需 vendor |
| 运行时依赖 | 零硬依赖，核心仅 stdlib | 守住「新机只有 python3 就能跑」的卖点 |
| 交互 UI | rich + questionary（失败降级纯文本） | 已验证，保留可降级能力 |
| 集成测试 | Docker（24.04，26.04 GA 后补） | 验证真实系统行为与幂等 |

---

## 2. 目录结构

```
bootstrap/
├── __init__.py
├── __main__.py            # python -m bootstrap → cli.main()
├── cli.py                 # argparse 入口、ensure_root、参数→任务选择
├── config/
│   ├── __init__.py
│   ├── schema.py          # Param / TaskSchema 定义 + 校验
│   └── loader.py          # TOML 加载 + 默认合并 + 校验 + 首次生成
├── core/
│   ├── __init__.py
│   ├── task.py            # Task 基类 + @task 装饰器 + Registry + CheckResult
│   ├── plan.py            # Step / Plan
│   ├── runner.py          # Runner.run(plan) -> Report
│   └── log.py             # Logger（终端+文件 tee）+ Report + JSON 导出
├── platform/              # 工具层（原 utils.py 拆分）
│   ├── __init__.py
│   ├── sys.py             # run_cmd / command_exists / package_installed / detect_codename / detect_arch / TaskError
│   ├── apt.py             # apt_install（进程内一次 update）
│   ├── fs.py              # read_lines / backup_write / backup_file / replace_or_append
│   └── user.py            # real_user / real_home
├── ui/
│   ├── __init__.py
│   ├── base.py            # Wizard 协议 + 依赖探测/安装
│   ├── tui.py             # rich + questionary 实现
│   └── plain.py           # ANSI 降级实现
└── tasks/
    ├── __init__.py        # 导入各任务模块，触发自动注册
    ├── apt_mirror.py
    ├── locale_timezone.py
    ├── system_update.py
    ├── base_tools.py
    ├── nvim.py
    ├── fzf.py
    ├── zsh.py
    ├── set_password.py
    └── ssh.py

config.example.toml
start.sh
pyproject.toml
tests/
├── unit/                  # 迁移自现有 tests/，适配新接口
└── integration/           # Docker 集成测试
    ├── Dockerfile.ubuntu2404
    └── test_bootstrap.py
docs/
└── DESIGN.md              # 本文档
```

> 说明：包名从 `lib` 改为 `bootstrap`，更语义化；`pyproject.toml` 的 `name` 保持 `ubuntu-bootstrap`。

---

## 3. 配置系统设计

### 3.1 分层模型

配置 = **内置默认（schema）← config.toml 覆盖 ← 向导运行时答案**，三层合并：

1. **schema 默认**：每个任务的 `Param` 声明里带 `default`（写死在代码中，保证"零配置也能跑"）。
2. **config.toml**：用户持久化覆盖（首次运行从 `config.example.toml` 复制生成）。
3. **运行时答案**：向导当场询问的答案，仅本次生效（可选 `--save` 回写 config.toml）。

合并结果生成一个**校验后的不可变 `Config` 对象**，任务只读它、从不写它。

### 3.2 TOML 结构（config.example.toml）

```toml
# config.example.toml —— Ubuntu 新机初始化配置

[apt]
mirror = "清华 TUNA"                 # 选 "不更改" 则跳过换源
mirrors = { "不更改" = "", "清华 TUNA" = "https://mirrors.tuna.tsinghua.edu.cn/ubuntu/", "阿里云" = "https://mirrors.aliyun.com/ubuntu/", "中科大" = "https://mirrors.ustc.edu.cn/ubuntu/", "华为云" = "https://repo.huaweicloud.com/ubuntu/" }

[system]
timezone = "Asia/Shanghai"
timezones = ["Asia/Shanghai", "Asia/Hong_Kong", "Asia/Tokyo", "UTC"]
locale = "zh_CN.UTF-8"
locales = ["zh_CN.UTF-8", "en_US.UTF-8"]

[base_tools]
packages = ["git", "curl", "wget", "htop", "build-essential", "unzip", "ca-certificates", "gnupg", "lsb-release", "software-properties-common"]
selected = []                         # 留空 = 安装全部候选

[password]
value = ""                            # 明文密码（仅 --all 非交互用），留空跳过

[zsh]
theme = "default"                     # default | random | powerlevel10k
plugins = ["git", "web-search", "z", "fzf", "zsh-autosuggestions", "zsh-syntax-highlighting"]
oh_my_zsh_url = "https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh"
external_plugins = { "zsh-autosuggestions" = "https://github.com/zsh-users/zsh-autosuggestions", "zsh-syntax-highlighting" = "https://github.com/zsh-users/zsh-syntax-highlighting" }
external_plugins_apt = { "zsh-autosuggestions" = "zsh-autosuggestions", "zsh-syntax-highlighting" = "zsh-syntax-highlighting" }
p10k_repo = "https://github.com/romkatv/powerlevel10k"

[nvim]
method = "apt"                        # apt | github

[fzf]
method = "apt"                        # apt | github

[ssh]
password_auth = true
permit_root_login = true

[ui]
pip_index_url = "https://pypi.tuna.tsinghua.edu.cn/simple"
packages = ["rich", "questionary"]
```

### 3.3 每任务参数声明（schema）

`Param` 是本次重写的核心概念：**任务不再是"读 cfg.XXX 的黑盒"，而是显式声明自己需要哪些参数**。向导、批量执行、校验、`--list` 展示、文档都从 `Param` 列表驱动。

```python
# bootstrap/config/schema.py

from dataclasses import dataclass, field
from typing import Any, Literal

@dataclass(frozen=True)
class Param:
    key: str                     # TOML 点路径，如 "apt.mirror"；与任务读取时同键
    type: Literal["str", "bool", "choice", "multi", "password"]
    default: Any                 # 内置默认值
    choices: tuple[str, ...] | str | None = None
                                 # 静态候选 tuple；或 "config:apt.mirrors" 引用配置目录
    label: str = ""              # 向导显示名
    help: str = ""               # 向导/文档说明
    interactive: bool = True     # False 时向导跳过、直接用 config 值

    def validate(self, value: Any) -> None: ...
    def normalize(self, raw: Any) -> Any: ...   # TOML 类型 -> 内部类型（如 "yes"/"no" -> bool）
```

**任务侧用法**：

```python
# bootstrap/tasks/apt_mirror.py

@task(
    id="apt_mirror",
    name="切换 apt 源为国内镜像",
    description="将 apt 源切换为配置的国内镜像（默认清华 TUNA）",
    depends_on=(),
    params=[
        Param("apt.mirror", "choice", default="清华 TUNA",
              choices="config:apt.mirrors", label="apt 镜像源"),
    ],
)
class AptMirrorTask(Task):
    def check(self, ctx: Context) -> CheckResult: ...
    def run(self, ctx: Context) -> None: ...
```

### 3.4 加载 / 合并 / 校验流程

```python
# bootstrap/config/loader.py

def load_config(path: str | None = None) -> Config:
    """1) 无 config.toml 则从 example 复制生成并提示；
       2) tomllib 解析；
       3) 与全任务 schema 的 default 合并（补缺失键）；
       4) 逐 Param 校验类型/候选（非法值报错并指出键名）；
       5) 未知键仅告警不报错（宽松，兼容用户自留字段）；
       6) 返回不可变 Config。"""
```

**Config 访问接口**：

```python
class Config(Mapping[str, Any]):
    def get(self, dotpath: str, default: Any = None) -> Any: ...  # "apt.mirror"
    def __getitem__(self, key: str) -> Any: ...                   # 段名，如 cfg["apt"]
    def as_dict(self) -> dict: ...
```

任务统一用 `ctx.config.get("apt.mirror")` 读取，键与 `Param.key` 一致。

---

## 4. 核心模块接口

> 以下为接口草图（类型与签名），非最终实现，但结构与职责已定。

### 4.1 core/task.py —— 任务基类 + 注册

```python
from abc import ABC, abstractmethod

@dataclass(frozen=True)
class CheckResult:
    done: bool
    note: str = ""

@dataclass(frozen=True)
class Context:
    config: Config
    log: Logger
    force: bool = False

class Task(ABC):
    meta: TaskMeta
    @abstractmethod
    def check(self, ctx: Context) -> CheckResult: ...
    @abstractmethod
    def run(self, ctx: Context) -> None: ...   # 失败抛 platform.TaskError

def task(*, id, name, description, depends_on=(), params=()):
    """类装饰器：注入 TaskMeta 并注册进 Registry。"""
    ...

class Registry:
    _registry: dict[str, type[Task]] = {}
    @classmethod
    def register(cls, task_cls): ...
    @classmethod
    def all(cls) -> list[Task]: ...    # 保持注册（导入）顺序
    @classmethod
    def get(cls, task_id: str) -> Task: ...
    @classmethod
    def all_params(cls) -> list[Param]: ...  # 供 loader 聚合校验
```

### 4.2 core/plan.py —— 计划模型（执行与表现的解耦点）

```python
@dataclass
class Step:
    task: Task
    answers: dict[str, Any]    # Param.key -> 运行时答案（覆盖 config）
    include: bool = True       # 向导里用户可跳过

@dataclass
class Plan:
    steps: list[Step]          # 已拓扑排序
    force: bool = False
    dry_run: bool = False
```

拓扑排序逻辑沿用现有 `topo_sort`（稳定、依赖在前、循环依赖报错），移入 `plan.py`。

### 4.3 core/runner.py —— 执行引擎

```python
@dataclass
class TaskResult:
    task_id: str
    status: Literal["ok", "skip", "fail"]
    note: str = ""

@dataclass
class Report:
    results: list[TaskResult]
    def summary(self) -> str: ...
    def to_json(self) -> str: ...

class Runner:
    def run(self, plan: Plan) -> Report:
        """对每个 include 的 Step：
           dry_run → 只记录待执行状态；
           否则 check → done 且非 force 则 skip；否则 run → ok/fail。
           子进程输出经 ctx.log.stream() tee 进日志。"""
```

### 4.4 core/log.py —— 日志（终端 + 文件 tee + 结果导出）

```python
class Logger:
    def __init__(self, log_dir: str): ...   # 创建 logs/YYYYmmdd-HHMMSS.log
    def log(self, msg: str = "", style: str | None = None) -> None:
        # 终端按 style 上色（非 TTY 纯文本），文件始终写纯文本
    def stream(self, line: str) -> None:
        # 子进程 stdout/stderr 逐行 tee：终端原样 + 文件落盘
    def close(self) -> None: ...
```

关键改进：`platform.sys.run_cmd` 增加 `tee=True` 模式，把子进程输出回调给 `Logger.stream`，使 `logs/` 真正包含 apt / git / curl 的实际输出（而非只记命令）。

### 4.5 platform/ —— 工具层拆分

| 模块 | 函数 | 说明 |
|---|---|---|
| `sys.py` | `run_cmd(cmd, *, check, capture, env, input_text, tee, log)` | 执行命令，支持 tee 输出回调；`FileNotFoundError` → TaskError |
| | `command_exists(name) -> bool` | PATH 探测 |
| | `package_installed(name) -> bool` | dpkg -s 静默探测 |
| | `detect_codename() -> str` | 读 /etc/os-release |
| | `detect_arch() -> str` | x86_64 / arm64 |
| | `TaskError` | 任务失败异常 |
| `apt.py` | `apt_install(packages, *, log)` | 进程内仅一次 `apt-get update`（去模块级全局，改实例化 `AptManager`） |
| `fs.py` | `read_lines / backup_write / backup_file / replace_or_append` | 原样迁移 |
| `user.py` | `real_user() / real_home()` | SUDO_USER 识别、pwd 回退 |

> `apt_install` 的 `_APT_UPDATED` 模块级全局改为显式的 `AptManager`（`Runner` 持有一个实例注入 `Context`），消除隐式共享状态、便于测试。

### 4.6 ui/ —— 表现层（只产出 Plan，不执行）

```python
# bootstrap/ui/base.py
class Wizard(Protocol):
    def build_plan(self, selected: list[Task], config: Config, *, force: bool) -> Plan: ...

def make_wizard(config: Config) -> Wizard:
    """TTY 且 rich/questionary 可用 → TuiWizard；否则 → PlainWizard。
       依赖缺失时先 ensure_deps 尝试 pip 安装，失败降级。"""
```

- `TuiWizard.build_plan` / `PlainWizard.build_plan`：逐个任务确认（默认未配置执行/已配置跳过）→ 问该任务 `interactive` 的 Param → 填 `answers` → 收集 `include`，最终返回 `Plan`。**不含任何执行逻辑**。
- 现有 `lib/tui.py` 的依赖探测/安装、ANSI 原语、展示原语、交互原语，拆入 `ui/`（表现层）与 `ui/tui.py`。

### 4.7 cli.py —— 入口

```python
def main() -> int:
    args = parse_args()          # --all/--only/--exclude/--list/--dry-run/--force/--yes/--save/--verbose
    ensure_root()                # 非 root 时 sudo 重执行自身（沿用）
    config = load_config()
    if args.list: print_task_list(config); return 0
    selected = select_tasks(args)        # all/only/exclude → list[Task]
    if args.only or args.all:            # 批量
        plan = batch_plan(selected, config, force=args.force, dry_run=args.dry_run)
    else:                                # 交互
        plan = make_wizard(config).build_plan(selected, config, force=args.force)
    report = Runner().run(plan)
    print_summary(report)
    if args.save: save_answers(plan)     # 可选回写 config.toml
    return 0 if report.all_ok() else 1
```

新增 CLI：`--exclude`（排除任务）、`--save`（向导答案回写 config.toml）、`--verbose`（日志更详细）。

---

## 5. 任务迁移清单

| 旧文件 | 新文件 | 迁移要点 |
|---|---|---|
| `init.py` | `bootstrap/cli.py` + `__main__.py` | `ensure_root`/`load_config`/`select_tasks` 拆入 cli 与 config；批量确认逻辑并入 `batch_plan` |
| `config.example.py` | `config.example.toml` + `bootstrap/config/*` | `QUESTIONS` 列表 → 每任务 `Param` 声明；常量 → TOML 分节 |
| `lib/tasks/base.py` | `bootstrap/core/task.py` | `check` 返回 `CheckResult`；`run(cfg, log)` → `run(ctx)`；新增 `@task` 装饰器 |
| `lib/tasks/__init__.py` | `bootstrap/tasks/__init__.py` | 手写 `REGISTRY` → 导入触发自动注册 |
| `lib/runner.py` | `bootstrap/core/{plan,runner,log}.py` | 拆 Plan/Runner/Logger；日志 tee + JSON；`_APT_UPDATED` 全局 → `AptManager` |
| `lib/ui.py` | `bootstrap/ui/{base,tui,plain}.py` | 两套向导合并为 `build_plan`，去掉执行耦合 |
| `lib/tui.py` | `bootstrap/ui/tui.py` | 依赖探测/ANSI/展示/交互原语归 ui 层 |
| `lib/utils.py` | `bootstrap/platform/{sys,apt,fs,user}.py` | 按职责拆四模块 |
| 9 个 `lib/tasks/*.py` | `bootstrap/tasks/*.py` | 迁到 `Param` 声明 + `ctx.config.get()` 读取 + `Context` 参数 |
| `tests/*` | `tests/unit/*` | 适配新接口：`CheckResult`、`Context`、`Config` 由 TOML 构建 |
| `README.md` | 更新 | 反映新 CLI、新配置、放弃 22.04 说明 |

**幂等与安全细节需原样保留**：备份写入、`sshd -T` 生效配置判定、drop-in 写 `/etc/ssh/sshd_config.d/99-bootstrap.conf`、`SUDO_USER` 真实用户识别、apt 优先 + GitHub 回退、p10k 跳过向导。

---

## 6. 分阶段落地计划

| 期 | 内容 | 产出 | 验收 |
|---|---|---|---|
| 一 · 地基 | `lib→bootstrap` 重命名、`pyproject.toml` 重写、config 三模块（schema/loader/TOML）、platform 拆分 | 新包骨架 + 配置系统 | 现有单测迁移后全绿；`load_config` 能解析并校验 TOML |
| 二 · 引擎 | `@task` 装饰器注册、`Plan`/`Runner`/`Logger(tee/JSON)`、三入口统一 | core 层 + cli | 批量执行等价于旧 `--all`；日志含子进程输出 |
| 三 · 任务迁移 | 9 个任务迁到新 schema/platform，逐任务保幂等；补 `--exclude`/`--save`/`--verbose`/网络重试 | 全部任务 | 每个任务 check/run 单测通过 |
| 四 · 集成测试 | Dockerfile(24.04) + 幂等断言（跑两遍第二遍全 skip）+ sshd/apt 源/locale 校验 + CI | integration/ | 容器内 `--all` 跑通且幂等 |
| 五 · 收尾 | README、任务模板、贡献指南、golden 快照测试 | 文档 + 模板 | 文档与实现一致 |

---

## 7. 风险与开放问题

1. **`Context` 引入的测试改动面**：所有任务 `check/run` 签名变化，三期迁移时需同步重写单测——一次性、可预期。
2. **`AptManager` 状态注入**：比模块级全局更清晰，但需保证 `Runner` 单次运行内共享同一实例。
3. **`--save` 回写 config.toml 的格式保持**：TOML 回写需保留注释/顺序，建议用「仅改值、保留其余文本」的最小 diff 策略，避免整体序列化丢注释（待一期验证可行性，不可行则 `--save` 降级为打印差异提示）。
4. **26.04 支持**：GA 前不承诺；`detect_codename` 的 deb822 判断改为「除 22.04 外均 deb822」的正向判定，避免硬编码 noble/resolute。
5. **golden 快照测试**：依赖终端渲染差异（rich 版本），建议只对「纯文本降级路径」做快照，避免脆断。

---

## 8. 评审清单

- [ ] 目录结构 / 包名 `bootstrap` 是否认可
- [ ] TOML 分节结构与键名是否认可（`[apt]` / `[system]` / `[zsh]` …）
- [ ] `Param` 声明式 schema 是否认可（替代 `QUESTIONS`）
- [ ] `Context` 取代 `check(cfg, log)` 签名是否认可
- [ ] `AptManager` 取代 `_APT_UPDATED` 全局是否认可
- [ ] `--save` 回写策略（最小 diff vs 打印差异）倾向
- [ ] 分阶段落地顺序是否认可
