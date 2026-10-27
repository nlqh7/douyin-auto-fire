from __future__ import annotations

import pytest

import app.webbridge as webbridge


def test_open_target_rejects_group_containing_friend_name(monkeypatch) -> None:
    responses = iter([
        {"x": 100, "y": 100},
        {"title": "莱茵河、测试账号、不良", "composer": True},
        {"title": "莱茵河、测试账号、不良", "composer": True},
    ])
    times = iter([0, 0, 11])
    monkeypatch.setattr(webbridge, "evaluate", lambda code: next(responses))
    monkeypatch.setattr(webbridge, "trusted_click", lambda rect: None)
    monkeypatch.setattr(webbridge.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(webbridge.time, "monotonic", lambda: next(times))

    with pytest.raises(webbridge.WebBridgeError, match="无法确认目标会话"):
        webbridge.open_target("不良")


def test_open_target_waits_for_refreshed_header(monkeypatch) -> None:
    responses = iter([
        {"x": 100, "y": 100},
        {"title": "上一个会话", "composer": True},
        {"title": "不良", "composer": True},
    ])
    monkeypatch.setattr(webbridge, "evaluate", lambda code: next(responses))
    monkeypatch.setattr(webbridge, "trusted_click", lambda rect: None)
    monkeypatch.setattr(webbridge.time, "sleep", lambda seconds: None)

    webbridge.open_target("不良")


def test_sticker_old_image_cannot_confirm_a_new_send(monkeypatch) -> None:
    responses = iter([
        {"anchor": "old", "content": "old-image"},
        {"x": 10, "y": 10},
        {"x": 20, "y": 20, "resource": "https://cdn.example.com/sticker.png"},
        {"x": 30, "y": 30},
        {"status": "unknown"},
    ])
    monkeypatch.setattr(webbridge, "evaluate", lambda code: next(responses))
    monkeypatch.setattr(webbridge, "trusted_click", lambda rect: None)
    monkeypatch.setattr(webbridge.time, "sleep", lambda seconds: None)

    with pytest.raises(webbridge.WebBridgeError, match="无法确认"):
        webbridge.send_sticker("续火花")


def test_sticker_requires_a_real_publish_button(monkeypatch) -> None:
    responses = iter([
        {"anchor": "old", "content": "old-image"},
        {"x": 10, "y": 10},
        {"x": 20, "y": 20, "resource": "https://cdn.example.com/sticker.png"},
        None,
    ])
    monkeypatch.setattr(webbridge, "evaluate", lambda code: next(responses))
    monkeypatch.setattr(webbridge, "trusted_click", lambda rect: None)
    monkeypatch.setattr(webbridge.time, "sleep", lambda seconds: None)

    with pytest.raises(webbridge.WebBridgeError, match="找不到发送按钮"):
        webbridge.send_sticker("续火花")
