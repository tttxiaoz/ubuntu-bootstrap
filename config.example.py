"""Ubuntu 初始化工具配置。

首次运行 init.py 时，若不存在 config.py 会从 config.example.py 复制生成。
本文件由用户按需修改。向导中可交互的配置项见下方 QUESTIONS。
"""

# ============ apt 源 ============
# 可选镜像源（向导中单选，字典键为显示名，值为镜像地址；值留空表示「不更改」）
# 镜像地址含 {codename} 占位符，会被替换为 jammy/noble/resolute
APT_MIRRORS = {
    "不更改": "",
    "清华 TUNA": "https://mirrors.tuna.tsinghua.edu.cn/ubuntu/",
    "阿里云": "https://mirrors.aliyun.com/ubuntu/",
    "中科大": "https://mirrors.ustc.edu.cn/ubuntu/",
    "华为云": "https://repo.huaweicloud.com/ubuntu/",
}
# 当前选中的镜像名（对应 APT_MIRRORS 的键；选「不更改」则跳过换源）
APT_MIRROR = "清华 TUNA"

# ============ 系统 ============
TIMEZONES = ["Asia/Shanghai", "Asia/Hong_Kong", "Asia/Tokyo", "UTC"]
TIMEZONE = "Asia/Shanghai"
LOCALES = ["zh_CN.UTF-8", "en_US.UTF-8"]
LOCALE = "zh_CN.UTF-8"

# ============ 基础工具 ============
BASE_PACKAGES = [
    "git", "curl", "wget", "htop", "build-essential", "unzip",
    "ca-certificates", "gnupg", "lsb-release", "software-properties-common",
]
# 实际安装的工具子集；留空表示「安装全部候选」，向导中可多选勾选
BASE_PACKAGES_SELECTED = []

# ============ 用户密码 ============
# 设置密码的目标用户：sudo 运行时为真实调用者，直接 root 运行时为 root。
# 交互式向导会安全地询问密码（不落盘）；--all 非交互时仅当此处显式填写才生效。
USER_PASSWORD = ""

# ============ zsh ============
OH_MY_ZSH_INSTALL_URL = "https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh"
# 主题： "default" | "random" | "powerlevel10k"
ZSH_THEME = "random"
ZSH_PLUGINS = ["git", "web-search", "z", "fzf", "zsh-autosuggestions", "zsh-syntax-highlighting"]
ZSH_EXTERNAL_PLUGINS = {
    "zsh-autosuggestions": "https://github.com/zsh-users/zsh-autosuggestions",
    "zsh-syntax-highlighting": "https://github.com/zsh-users/zsh-syntax-highlighting",
}
POWERLEVEL10K_REPO = "https://github.com/romkatv/powerlevel10k"

# ============ 编辑器 / 工具 ============
NEOVIM_INSTALL_METHOD = "apt"   # "apt" | "github"
FZF_INSTALL_METHOD = "apt"      # "apt" | "github"

# ============ SSH ============
# ⚠️ 安全提示：公网服务器若同时开启「密码认证 + root 直接登录」，有被暴力破解的风险。
# 更安全的做法是改用密钥登录，并把下面两项设为 "no"。
SSH_PASSWORD_AUTH = "yes"       # sshd 密码认证
SSH_PERMIT_ROOT_LOGIN = "yes"   # 允许 root 登录

# ============ 交互 UI（rich + questionary） ============
# 向导界面由 rich（彩色展示）+ questionary（单选/确认）驱动。
# 首次运行若缺失会通过 pip 自动安装；失败自动降级为 ANSI 彩色纯文本，功能不受影响。
# 国内可将 PIP_INDEX_URL 改为清华/阿里 pip 镜像加速。
PIP_INDEX_URL = "https://pypi.tuna.tsinghua.edu.cn/simple"
TUI_PACKAGES = ["rich", "questionary"]


# ============ 向导交互项 ============
# 每一项描述向导中的一个交互配置。
#   id          唯一标识
#   name        向导中显示的标题
#   type        "choice"（单选）| "bool"（是/否，写 "yes"/"no"）| "multi"（多选，写 list）| "password"（密码，不落盘）
#   options     候选：以 "@" 开头表示引用上方同名变量（dict 取 keys 保序，list 直接取）；否则为静态列表
#   config_key  选中的值写回 config 的同名属性
#   task        关联的任务 id（向导到达该任务时展示此配置项）
#   interactive 设为 False 时向导跳过该项、直接用 config 中的值
QUESTIONS = [
    {"id": "apt_mirror", "name": "apt 镜像源", "type": "choice",
     "options": "@APT_MIRRORS", "config_key": "APT_MIRROR",
     "task": "apt_mirror", "interactive": True},
    {"id": "timezone", "name": "时区", "type": "choice",
     "options": "@TIMEZONES", "config_key": "TIMEZONE",
     "task": "locale_timezone", "interactive": True},
    {"id": "locale", "name": "系统语言", "type": "choice",
     "options": "@LOCALES", "config_key": "LOCALE",
     "task": "locale_timezone", "interactive": True},
    {"id": "base_packages", "name": "要安装的基础工具", "type": "multi",
     "options": "@BASE_PACKAGES", "config_key": "BASE_PACKAGES_SELECTED",
     "task": "base_tools", "interactive": True},
    {"id": "zsh_theme", "name": "zsh 主题", "type": "choice",
     "options": ["default", "random", "powerlevel10k"],
     "config_key": "ZSH_THEME", "task": "zsh", "interactive": True},
    {"id": "nvim_method", "name": "neovim 安装方式", "type": "choice",
     "options": ["apt", "github"], "config_key": "NEOVIM_INSTALL_METHOD",
     "task": "nvim", "interactive": True},
    {"id": "fzf_method", "name": "fzf 安装方式", "type": "choice",
     "options": ["apt", "github"], "config_key": "FZF_INSTALL_METHOD",
     "task": "fzf", "interactive": True},
    {"id": "user_password", "name": "设置用户密码", "type": "password",
     "config_key": "USER_PASSWORD", "task": "set_password", "interactive": True},
    {"id": "ssh_password", "name": "SSH 密码认证", "type": "bool",
     "config_key": "SSH_PASSWORD_AUTH", "task": "ssh", "interactive": True},
    {"id": "ssh_root", "name": "允许 root 登录", "type": "bool",
     "config_key": "SSH_PERMIT_ROOT_LOGIN", "task": "ssh", "interactive": True},
]
