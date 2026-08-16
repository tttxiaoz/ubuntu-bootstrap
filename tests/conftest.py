import os
import sys

# 让 pytest 能从仓库根目录导入 lib 包（兼容未配置 pythonpath 的旧 pytest）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
