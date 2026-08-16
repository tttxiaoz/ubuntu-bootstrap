# Ubuntu 新机初始化工具

一键/按需配置新装 Ubuntu 服务器的基础环境。纯 Python 标准库实现，零 pip 依赖，Ubuntu 22.04 / 24.04 / 26.04 均自带 python3 可直接运行。

## 快速开始（新服务器上一键拉取并执行）

```bash
# 拉取代码并进入目录
git clone https://github.com/tttxiaoz/ubuntu-bootstrap.git
cd ubuntu-bootstrap

# 一键执行全部任务（推荐）
./start.sh --all

# 或交互式向导按需选择
./start.sh
```

> 公开仓库，无需认证，直接 clone 即可。脚本用纯 Python 标准库，Ubuntu 自带 python3，零额外依赖。

## 功能

| 任务 | 说明 |
|---|---|
| apt 源切换 | 换国内镜像（默认清华 TUNA，可在 config.py 改），兼容 22.04 的 `sources.list` 与 24.04/26.04 的 deb822 `.sources` |
| 时区与 locale | 时区 Asia/Shanghai，locale zh_CN.UTF-8 |
| 系统更新 | `apt-get update && upgrade` |
| 基础工具 | git / curl / wget / htop / build-essential 等 |
| neovim | 安装 neovim，并将 vi/vim 指向 nvim |
| fzf | 安装命令行模糊查找工具 |
| zsh | zsh + oh-my-zsh + 插件（git / web-search / z / zsh-autosuggestions / zsh-syntax-highlighting）+ 主题（default / random / powerlevel10k） |
| SSH | openssh-server + 密码认证 + 允许 root 登录 + 放行 22 端口 |

每个任务执行前都会**先检测是否已配置**，已配置的自动跳过（幂等）；菜单中也会实时显示每个任务的当前状态。

## 使用

先按上方「快速开始」拉取代码并进入目录，然后：

### 启动脚本 start.sh

```bash
./start.sh                  # 交互式向导（推荐）
./start.sh --all            # 一键执行全部任务
./start.sh --only zsh,nvim  # 仅执行指定任务（id 见 --list）
./start.sh --list           # 查看任务及当前状态
./start.sh --dry-run --all  # 预览执行顺序，不实际执行
./start.sh --force --all    # 强制重跑（忽略幂等判断）
./start.sh --help           # 显示帮助
```

`start.sh` 只是 `init.py` 的便捷入口：定位脚本目录、检查 python3、透传参数。权限提升仍由 `init.py` 自动完成（非 root 时通过 sudo 重新执行自身），所以无需手动加 `sudo`。

也可以直接运行 `python3 init.py ...`，两者等价。

### 向导操作说明

- 每个配置项单独一屏，显示名称、说明、当前状态（已配置/未配置）。
- 用 **←/→ 或空格** 切换「启用 / 跳过」。
- **回车** 进入下一项，**b** 返回上一项；最后一项回车进入汇总确认。
- 已配置的项目默认「跳过」，未配置的默认「启用」，一路回车即可接受推荐。
- 汇总页会列出将执行/跳过的清单，**回车** 开始、**b** 返回修改、**q** 退出。

## 配置

首次运行会自动从 `config.example.py` 复制生成 `config.py`，按需修改：

- `APT_MIRROR_URL`：镜像地址（清华/阿里/中科大）
- `ZSH_THEME`：`default` / `random` / `powerlevel10k`
- `ZSH_PLUGINS`：插件列表
- `NEOVIM_INSTALL_METHOD` / `FZF_INSTALL_METHOD`：`apt` 或 `github`
- `SSH_PASSWORD_AUTH` / `SSH_PERMIT_ROOT_LOGIN`：SSH 开关

## 说明

- 需要 root 权限，脚本会自动通过 `sudo` 重新执行自身。
- 通过 `SUDO_USER` 识别真实用户，zsh/oh-my-zsh 配置作用于该用户（而非 root）。
- 所有系统配置文件写入前会先备份为 `*.bak`。
- powerlevel10k 主题会跳过首次交互向导；完整字形显示需要 Nerd Font 终端，可另跑 `p10k configure`。
- 22.04 仓库的 neovim 版本较旧，如需新版可在 config.py 设 `NEOVIM_INSTALL_METHOD = "github"`。
