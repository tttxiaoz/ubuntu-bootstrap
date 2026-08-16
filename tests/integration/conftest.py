"""Docker 集成测试：镜像构建与容器运行辅助。"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INTEGRATION_DIR = Path(__file__).parent
IMAGE = "ubuntu-bootstrap-test:24.04"


def _docker(args: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], **kw)


@pytest.fixture(scope="session")
def image() -> str:
    """构建一次测试镜像（会话级复用）。"""
    if shutil.which("docker") is None:
        pytest.skip("docker 不可用，跳过集成测试")
    dockerfile = INTEGRATION_DIR / "Dockerfile.ubuntu2404"
    # DOCKER_BUILDKIT=0 兼容部分 buildx 配置异常的宿主机
    env = {**os.environ, "DOCKER_BUILDKIT": "0"}
    _docker(["build", "-q", "-t", IMAGE, "-f", str(dockerfile), str(INTEGRATION_DIR)],
            check=True, env=env)
    return IMAGE


@pytest.fixture
def run_in_container(image):
    """返回一个在一次性容器里执行 shell 脚本的函数（仓库以 /app 挂载）。"""

    def _run(script: str) -> str:
        result = _docker(["run", "--rm", "-v", f"{REPO_ROOT}:/app", "-w", "/app",
                          image, "bash", "-c", script], capture_output=True, text=True)
        return (result.stdout or "") + (result.stderr or "")

    return _run
