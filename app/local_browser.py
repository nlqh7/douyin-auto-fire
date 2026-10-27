from __future__ import annotations

import os
from pathlib import Path


def find_system_browser(browser_id: str | None = None) -> str | None:
    candidates_by_browser = {
        "chrome": (
            Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
        ),
        "edge": (
            Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/Application/msedge.exe",
        ),
    }
    if browser_id is not None and browser_id not in candidates_by_browser:
        raise ValueError("仅支持 Chrome 或 Edge")
    browser_ids = (browser_id,) if browser_id else ("chrome", "edge")
    for current_id in browser_ids:
        for path in candidates_by_browser[current_id]:
            if path.is_file():
                return str(path)
    return None
