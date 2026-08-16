"""在真实 Ubuntu 24.04 容器内验证启动、dry-run 与任务幂等。"""

from __future__ import annotations


def test_list_smoke(run_in_container):
    out = run_in_container("python3 -m bootstrap --list")
    assert "apt_mirror" in out
    assert "ssh" in out
    assert "未配置" in out or "已配置" in out


def test_dry_run_all_smoke(run_in_container):
    out = run_in_container("python3 -m bootstrap --dry-run --all --yes")
    assert "DRY-RUN" in out
    assert "apt_mirror" in out
    assert "system_update" in out


def test_apt_mirror_rewrites_deb822_and_is_idempotent(run_in_container):
    script = (
        "rm -f config.toml; "
        "python3 -m bootstrap --only apt_mirror --yes 2>&1; "
        "echo '===SECOND==='; "
        "python3 -m bootstrap --only apt_mirror --yes 2>&1; "
        "echo '===SOURCES==='; "
        "cat /etc/apt/sources.list.d/ubuntu.sources"
    )
    out = run_in_container(script)

    # 源文件被改写为清华镜像
    sources = out.split("===SOURCES===", 1)[1]
    assert "mirrors.tuna.tsinghua.edu.cn" in sources

    # 第二次执行应幂等跳过
    second = out.split("===SECOND===", 1)[1].split("===SOURCES===", 1)[0]
    assert ("跳过" in second) or ("已指向镜像源" in second)
