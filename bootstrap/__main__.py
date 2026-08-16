"""python -m bootstrap 入口。"""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断，退出。")
        sys.exit(130)
