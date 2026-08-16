"""Ubuntu 初始化工具配置。

首次运行 init.py 时，若不存在 config.py 会从 config.example.py 复制生成。
本文件由用户按需修改。
"""

# ============ apt 源 ============
# 镜像地址模板，{codename} 会被替换为 jammy/noble/resolute
# 国内可选：
#   清华  https://mirrors.tuna.tsinghua.edu.cn/ubuntu/
#   阿里  https://mirrors.aliyun.com/ubuntu/
#   中科大 https://mirrors.ustc.edu.cn/ubuntu/
APT_MIRROR_URL = "https://mirrors.tuna.tsinghua.edu.cn/ubuntu/"

# ============ 系统 ============
TIMEZONE = "Asia/Shanghai"
LOCALE = "zh_CN.UTF-8"

# ============ 基础工具 ============
BASE_PACKAGES = [
    "git", "curl", "wget", "htop", "build-essential", "unzip",
    "ca-certificates", "gnupg", "lsb-release", "software-properties-common",
]

# ============ zsh ============
OH_MY_ZSH_INSTALL_URL = "https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh"
# 主题： "default" | "random" | "powerlevel10k"
ZSH_THEME = "random"
ZSH_PLUGINS = ["git", "web-search", "z", "zsh-autosuggestions", "zsh-syntax-highlighting"]
ZSH_EXTERNAL_PLUGINS = {
    "zsh-autosuggestions": "https://github.com/zsh-users/zsh-autosuggestions",
    "zsh-syntax-highlighting": "https://github.com/zsh-users/zsh-syntax-highlighting",
}
POWERLEVEL10K_REPO = "https://github.com/romkatv/powerlevel10k"

# ============ 编辑器 / 工具 ============
NEOVIM_INSTALL_METHOD = "apt"   # "apt" | "github"
FZF_INSTALL_METHOD = "apt"      # "apt" | "github"

# ============ SSH ============
SSH_PASSWORD_AUTH = "yes"       # sshd 密码认证
SSH_PERMIT_ROOT_LOGIN = "yes"   # 允许 root 登录
