from __future__ import annotations

from pathlib import Path

import pytest

from app.local_browser import find_system_browser
from app.profile_browser import default_browser_profile


def _profile_environment(monkeypatch, tmp_path: Path, prog_id: str) -> None:
    monkeypatch.setattr("app.profile_browser._windows_default_prog_id", lambda: prog_id)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))


def test_default_chrome_uses_chrome_executable_and_profile(monkeypatch, tmp_path) -> None:
    _profile_environment(monkeypatch, tmp_path, "ChromeHTML.TEST")
    profile_dir = tmp_path / "Google" / "Chrome" / "User Data"
    profile_dir.mkdir(parents=True)
    monkeypatch.setattr("app.profile_browser.find_system_browser", lambda browser_id: f"{browser_id}.exe")

    profile = default_browser_profile()

    assert profile.browser_id == "chrome"
    assert profile.executable_path == "chrome.exe"
    assert profile.user_data_dir == profile_dir


def test_default_edge_uses_edge_executable_and_profile(monkeypatch, tmp_path) -> None:
    _profile_environment(monkeypatch, tmp_path, "MSEdgeHTM")
    profile_dir = tmp_path / "Microsoft" / "Edge" / "User Data"
    profile_dir.mkdir(parents=True)
    monkeypatch.setattr("app.profile_browser.find_system_browser", lambda browser_id: f"{browser_id}.exe")

    profile = default_browser_profile()

    assert profile.browser_id == "edge"
    assert profile.name == "Edge"
    assert profile.executable_path == "edge.exe"
    assert profile.user_data_dir == profile_dir


def test_non_chromium_default_browser_is_rejected(monkeypatch, tmp_path) -> None:
    _profile_environment(monkeypatch, tmp_path, "FirefoxURL.TEST")

    with pytest.raises(RuntimeError, match="不是 Chrome 或 Edge"):
        default_browser_profile()


def test_browser_lookup_can_select_edge_explicitly(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROGRAMFILES", str(tmp_path))
    monkeypatch.setenv("PROGRAMFILES(X86)", "")
    monkeypatch.setenv("LOCALAPPDATA", "")
    chrome = tmp_path / "Google" / "Chrome" / "Application" / "chrome.exe"
    edge = tmp_path / "Microsoft" / "Edge" / "Application" / "msedge.exe"
    chrome.parent.mkdir(parents=True)
    edge.parent.mkdir(parents=True)
    chrome.touch()
    edge.touch()

    assert find_system_browser("chrome") == str(chrome)
    assert find_system_browser("edge") == str(edge)
    assert find_system_browser() == str(chrome)
