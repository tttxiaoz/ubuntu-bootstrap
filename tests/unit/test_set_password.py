"""set_password 任务的密码状态解析与设置逻辑测试。"""

from __future__ import annotations

from types import SimpleNamespace

from bootstrap.tasks import set_password as sp
from bootstrap.tasks.set_password import SetPasswordTask


class _Proc(SimpleNamespace):
    def __init__(self, stdout="", returncode=0):
        super().__init__(stdout=stdout, returncode=returncode)


def test_password_status_usable(monkeypatch):
    monkeypatch.setattr(sp.psys, "run_cmd",
                        lambda *a, **k: _Proc("root P 01/01/2022 0 99999 7 -1\n"))
    assert SetPasswordTask._password_status("root") == "P"


def test_password_status_locked(monkeypatch):
    monkeypatch.setattr(sp.psys, "run_cmd",
                        lambda *a, **k: _Proc("root L 01/01/2022 0 99999 7 -1\n"))
    assert SetPasswordTask._password_status("root") == "L"


def test_check_reports_configured(monkeypatch, make_ctx):
    monkeypatch.setattr(sp.user, "real_user", lambda: "root")
    monkeypatch.setattr(sp.psys, "run_cmd",
                        lambda *a, **k: _Proc("root P 01/01/2022 0 99999 7 -1\n"))
    res = SetPasswordTask().check(make_ctx())
    assert res.done is True


def test_run_sets_password_via_chpasswd(monkeypatch, make_ctx):
    calls = []
    monkeypatch.setattr(sp.user, "real_user", lambda: "root")
    monkeypatch.setattr(sp.psys, "run_cmd",
                        lambda cmd, **kw: calls.append((cmd, kw)) or _Proc())
    SetPasswordTask().run(make_ctx({"password": {"value": "secret"}}))
    chpasswd = [c for c in calls if c[0] and c[0][0] == "chpasswd"]
    assert chpasswd, "应调用 chpasswd"
    assert chpasswd[0][1]["input_text"] == "root:secret\n"


def test_run_skips_without_password(monkeypatch, make_ctx):
    calls = []
    monkeypatch.setattr(sp.user, "real_user", lambda: "root")
    monkeypatch.setattr(sp.psys, "run_cmd",
                        lambda cmd, **kw: calls.append(cmd) or _Proc())
    SetPasswordTask().run(make_ctx({"password": {"value": ""}}))
    assert not any(c and c[0] == "chpasswd" for c in calls)
