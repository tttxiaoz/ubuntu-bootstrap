#!/usr/bin/env bash
# Ubuntu 新机初始化工具启动脚本
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Ubuntu 新机初始化工具

用法：
  ./start.sh                  # 交互式向导（推荐）
  ./start.sh --all            # 一键执行全部任务
  ./start.sh --only zsh,nvim  # 仅执行指定任务（id 见 --list）
  ./start.sh --exclude ssh    # 排除指定任务
  ./start.sh --list           # 查看任务及当前状态
  ./start.sh --dry-run --all  # 预览执行顺序，不实际执行
  ./start.sh --force --all    # 强制重跑（忽略幂等判断）
  ./start.sh --yes --all      # 跳过执行前确认
  ./start.sh --help           # 显示本帮助

更多说明见 README.md
EOF
}

# 帮助
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || "${1:-}" == "help" ]]; then
  usage
  exit 0
fi

# 检查 python3（24.04+ 自带 3.12）
if ! command -v python3 >/dev/null 2>&1; then
  echo "错误：未找到 python3，请先安装（Ubuntu 默认自带）。" >&2
  exit 1
fi

# 切换到脚本所在目录（保证无论从何处调用，相对路径都正确）
cd "$SCRIPT_DIR"

# 执行（cli.py 内部会自动通过 sudo 提升权限）
exec python3 -m bootstrap "$@"
