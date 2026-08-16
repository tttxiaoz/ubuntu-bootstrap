# Ubuntu 新机初始化工具

一键/按需配置新装 Ubuntu 服务器的基础环境。核心用 Python 标准库实现，交互界面依赖（rich / questionary）在首次运行时自动通过 pip 准备（失败自动降级纯文本）。

> 目标 Ubuntu **24.04+**（Python 3.12+，自带 `tomllib`），零运行时依赖、零 vendor。

## 快速开始（新服务器上一键拉取并执行）

```bash
# 拉取代码并进入目录（国内推荐用 Gitee，速度快）
git clone https://gitee.com/tttxiaoz/ubuntu-bootstrap.git
# 或 GitHub：git clone https://github.com/tttxiaoz/ubuntu-bootstrap.git
cd ubuntu-bootstrap

# 一键执行全部任务（推荐）
./start.sh --all

# 或交互式向导按需选择
./start.sh
```

> 公开仓库，无需认证，直接 clone 即可。核心用 Python 标准库，Ubuntu 自带 python3；交互 UI 依赖会在首次运行时自动 pip 安装，无需手动操作。

## 仓库镜像

| 平台 | 地址 |
|---|---|
| GitHub | https://github.com/tttxiaoz/ubuntu-bootstrap |
| Gitee | https://gitee.com/tttxiaoz/ubuntu-bootstrap |

两处内容一致，国内网络环境下推荐使用 Gitee。

## 功能

| 任务 | 说明 |
|---|---|
| apt 源切换 | 换国内镜像（默认清华 TUNA，可选「不更改」保持原样），兼容 deb822 `.sources`（24.04+）与经典 `sources.list` |
| 系统更新 | `apt-get update && upgrade` |
| 设置用户密码 | 为当前用户（sudo 时真实用户 / root 时 root）设置登录密码，交互式输入、不落盘 |
| SSH | openssh-server + 按配置设置密码认证 / root 登录 + 重启生效并放行 22 端口（默认开启，见下方安全说明） |
| 时区与 locale | 时区 Asia/Shanghai，locale zh_CN.UTF-8 |
| 基础工具 | git / curl / wget / htop / build-essential 等（向导可多选） |
| fzf | 安装命令行模糊查找工具 |
| neovim | 安装 neovim，并将 vi/vim 指向 nvim |
| zsh | zsh + oh-my-zsh + 插件（git / web-search / z / fzf / zsh-autosuggestions / zsh-syntax-highlighting）+ 主题（default / random / powerlevel10k） |

每个任务执行前都会**先检测是否已配置**，已配置的自动跳过（幂等）；菜单中也会实时显示每个任务的当前状态。

## 使用

先按上方「快速开始」拉取代码并进入目录，然后：

### 启动脚本 start.sh

```bash
./start.sh                  # 交互式向导（推荐）
./start.sh --all            # 一键执行全部任务
./start.sh --only zsh,nvim  # 仅执行指定任务（id 见 --list）
./start.sh --exclude ssh    # 排除指定任务
./start.sh --list           # 查看任务及当前状态
./start.sh --dry-run --all  # 预览执行顺序，不实际执行
./start.sh --force --all    # 强制重跑（忽略幂等判断）
./start.sh --yes --all      # 跳过执行前确认
./start.sh --help           # 显示帮助
```

`start.sh` 只是 `python3 -m bootstrap` 的便捷入口：定位脚本目录、检查 python3、透传参数。权限提升由 `bootstrap/cli.py` 自动完成（非 root 时通过 sudo 重新执行自身），所以无需手动加 `sudo`。

### 向导操作说明

- 向导**逐步执行**：确认一个任务 →（可选）选择该任务的配置项 → 立即执行 → 进入下一个任务。
- 界面由 **rich + questionary** 驱动，提供彩色标题、面板、单选/确认框。
- 有配置项的任务（如镜像源、时区、zsh 主题、SSH 开关）会在执行前用方向键单选 / 确认框选择。
- 已配置的任务默认「跳过」，未配置的默认「执行」。
- 执行时命令输出（如 apt 进度）会实时显示在终端，并同步写入 `logs/`。
- 任意时刻按 `Ctrl+C` 即可安全中断退出（已执行的内容会记录在 `logs/`）。

### 关于交互 UI 依赖

向导界面依赖 `rich` + `questionary`（纯 Python 库）。**首次运行会自动用 pip 安装**到系统 Python；PEP 668 限制会自动处理。

- 国内网络慢可在 `config.toml` 里把 `ui.pip_index_url` 改为清华/阿里 pip 镜像（默认已是清华）。
- 若 pip 安装失败，工具会**自动降级为 ANSI 彩色纯文本模式**，功能不受影响。
- 也可提前手动安装：`pip install rich questionary`（需加 `--break-system-packages`）。

## 配置

首次运行会自动从 `config.example.toml` 复制生成 `config.toml`（TOML 格式），按需修改：

- `[apt]` `mirror` / `mirrors`：镜像源候选与当前选择
- `[system]` `timezone` / `timezones`、`locale` / `locales`：时区与语言候选
- `[base_tools]` `packages` / `selected`：基础工具候选与选中子集（`selected` 留空=安装全部）
- `[zsh]` `theme`：`default` / `random` / `powerlevel10k`；`plugins` 插件列表；外部插件与 apt 包映射
- `[password]` `value`：非交互（`--all`）时用于设置用户密码（可选，明文存储请自行权衡）
- `[ssh]` `password_auth` / `permit_root_login`：SSH 开关（布尔）
- `[ui]` `pip_index_url` / `packages`：交互 UI 依赖的 pip 源与包列表

> 每个任务在代码里声明自己的配置参数（类型/候选/默认/是否交互），向导、批量执行、校验、`--list` 展示都由这份声明驱动；`config.toml` 里额外的键会被宽松忽略、缺失的键自动用默认值补齐。

## 说明

- 需要 root 权限，脚本会自动通过 `sudo` 重新执行自身。
- 安装方式原则：**一律用 apt**（neovim / fzf / zsh 插件均走 apt，更快、可用国内镜像）；仅 apt 源没有的（oh-my-zsh、powerlevel10k）才从 GitHub 获取。
- 通过 `SUDO_USER` 识别真实用户，zsh/oh-my-zsh 配置作用于该用户（而非 root）。
- 所有系统配置文件写入前会先备份为 `*.bak`。
- powerlevel10k 主题会跳过首次交互向导；完整字形显示需要 Nerd Font 终端，可另跑 `p10k configure`。

### 无 TTY 环境（headless）

`./start.sh --all` / `--only` 在无交互终端（如 `ssh host './start.sh --all'`、cloud-init）下会**自动确认执行**；如需完全静默输出可加 `--yes`。

### SSH 安全建议

SSH 任务默认沿用「密码认证 + 允许 root 登录」（`password_auth = true`、`permit_root_login = true`），方便新机快速登录，但公网暴露下有被暴力破解的风险。生产环境建议：

- 改用密钥登录，并在 `config.toml` 把 `ssh.password_auth` / `ssh.permit_root_login` 设为 `false`；
- 或通过 `ufw` 限制来源 IP（脚本默认放行 22 端口）。

当上述任一项保持 `true` 时，任务执行会打印醒目的安全提醒。

> 实现上，SSH 配置写入 `/etc/ssh/sshd_config.d/99-bootstrap.conf`（高优先级 drop-in），可覆盖 cloud-init 等写入的默认值；状态判定用 `sshd -T` 读取**生效**配置，避免漏判被 drop-in 覆盖的情况。

### 任务幂等性

除「更新系统」外的任务均幂等（已配置自动跳过）。「更新系统」任务无持久状态、每次运行都会执行 `apt-get update + upgrade`（在 `--list` 中恒显示「未配置」属正常）。

## 目录结构

```
bootstrap/          主包
├── cli.py          命令行入口
├── config/         TOML 配置：Param 声明 + 加载校验
├── core/           Task/@task 注册、Plan、Runner、Logger
├── platform/       工具层：sys / apt / fs / user
├── ui/             ANSI、终端原语、向导（只产出 Plan）
└── tasks/          9 个初始化任务
config.example.toml 配置模板
tests/              单元测试（unit/）与集成测试（integration/，Docker）
```

## 开发与测试

运行时依赖 `rich` / `questionary` 会自动安装（缺失可降级）；开发测试需要 Python 3.11+ 与 `pip install -e '.[dev]'`（含 pytest / ruff / tomli 回退）：

```bash
pytest                      # 运行全部测试（单元 + Docker 集成）
pytest tests/unit           # 仅单元测试
pytest tests/integration    # 仅 Docker 集成测试（需 Docker 守护进程）
ruff check .                # 静态检查
```

> 更多约定与「新增任务」模板见 [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md)。

> 说明：目标机（Ubuntu 24.04+，Python 3.12+）的 TOML 配置解析走 stdlib `tomllib`；`<3.11` 的开发机会通过 `tomli` 回退（仅开发依赖，目标机不受影响）。
