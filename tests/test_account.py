from __future__ import annotations

import json

import app.account as account


def test_cached_account_and_scan_status(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(account, "DATA_DIR", tmp_path)
    monkeypatch.setattr(account, "ACCOUNT_PATH", tmp_path / "account.json")
    monkeypatch.setattr(account, "SCAN_PATH", tmp_path / "scan-status.json")
    account.ACCOUNT_PATH.write_text(json.dumps({"name": "测试账号"}), encoding="utf-8")
    account.SCAN_PATH.write_text(json.dumps({"count": 2, "targets": ["甲", "乙"]}), encoding="utf-8")
    monkeypatch.setattr(account, "command", lambda *args: (_ for _ in ()).throw(AssertionError("不应访问浏览器")))

    result = account.account_status()

    assert result["account"]["name"] == "测试账号"
    assert result["scan"]["count"] == 2
    assert result["scan"]["targets"] == ["甲", "乙"]


def test_missing_account_does_not_open_browser(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(account, "ACCOUNT_PATH", tmp_path / "account.json")
    monkeypatch.setattr(account, "SCAN_PATH", tmp_path / "scan-status.json")
    monkeypatch.setattr(account, "refresh_account", lambda: (_ for _ in ()).throw(AssertionError("状态读取不应访问浏览器")))

    result = account.account_status()
    second = account.account_status()

    assert result["account"] == {"name": "", "avatar": None}
    assert second["scan"]["count"] is None


def test_refresh_keeps_previous_avatar_when_download_fails(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(account, "DATA_DIR", tmp_path)
    monkeypatch.setattr(account, "ACCOUNT_PATH", tmp_path / "account.json")
    monkeypatch.setattr(account, "AVATAR_PATH", tmp_path / "douyin-avatar.jpg")
    account.AVATAR_PATH.write_bytes(b"previous avatar")
    monkeypatch.setattr(account, "command", lambda *args: {})
    monkeypatch.setattr(account, "evaluate", lambda code: {"name": "测试账号", "avatar": "https://example.com/new.jpg"})
    monkeypatch.setattr(account, "save_avatar", lambda url: False)
    monkeypatch.setattr(account, "ensure_chat", lambda: None)

    result = account.refresh_account()

    assert result["name"] == "测试账号"
    assert result["avatar"] == "douyin-avatar.jpg"
    assert result["refreshed_at"]
    assert account.AVATAR_PATH.read_bytes() == b"previous avatar"
    assert json.loads(account.ACCOUNT_PATH.read_text(encoding="utf-8")) == result


def test_scan_from_previous_day_is_not_shown_as_pending_today(monkeypatch, tmp_path) -> None:
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    monkeypatch.setattr(account, "ACCOUNT_PATH", tmp_path / "account.json")
    monkeypatch.setattr(account, "SCAN_PATH", tmp_path / "scan-status.json")
    account.ACCOUNT_PATH.write_text(json.dumps({"name": "测试账号"}), encoding="utf-8")
    yesterday = datetime.now(ZoneInfo("Asia/Shanghai")) - timedelta(days=1)
    account.SCAN_PATH.write_text(json.dumps({"count": 5, "targets": ["甲"], "scanned_at": yesterday.isoformat()}), encoding="utf-8")

    result = account.account_status()

    assert result["scan"] == {"count": None, "targets": [], "stale": True}


def test_avatar_download_stays_local_and_is_optional(monkeypatch, tmp_path) -> None:
    from io import BytesIO
    from email.message import Message

    headers = Message()
    headers["Content-Type"] = "image/jpeg"
    response = BytesIO(b"avatar")
    response.headers = headers
    response.url = "https://cdn.example.com/avatar.jpg"
    response.__enter__ = lambda: response
    response.__exit__ = lambda *args: None
    monkeypatch.setattr(account, "AVATAR_PATH", tmp_path / "douyin-avatar.jpg")
    monkeypatch.setattr(account, "urlopen", lambda *args, **kwargs: response)

    assert account.save_avatar("//cdn.example.com/avatar.jpg")
    assert account.AVATAR_PATH.read_bytes() == b"avatar"

    monkeypatch.setattr(account, "urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("offline")))
    assert not account.save_avatar("https://example.com/other.jpg")
    assert account.AVATAR_PATH.read_bytes() == b"avatar"
    assert not account.save_avatar("file:///outside-project.jpg")
