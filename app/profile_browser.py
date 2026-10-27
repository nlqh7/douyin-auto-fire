from __future__ import annotations

from dataclasses import dataclass
import os
from contextlib import asynccontextmanager
from pathlib import Path

from playwright.async_api import async_playwright

from app.browser import BrowserSession
from app.local_browser import find_system_browser


@dataclass(frozen=True)
class DefaultBrowserProfile:
    browser_id: str
    name: str
    executable_path: str
    user_data_dir: Path


def _windows_default_prog_id() -> str:
    if os.name != "nt":
        raise RuntimeError("系统默认浏览器模式目前仅支持 Windows")
    import winreg

    key_path = r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _ = winreg.QueryValueEx(key, "ProgId")
    except OSError as exc:
        raise RuntimeError("无法识别系统默认浏览器，请改用 Kimi WebBridge 或独立浏览器模式") from exc
    return str(value)


def default_browser_profile() -> DefaultBrowserProfile:
    prog_id = _windows_default_prog_id().lower()
    if prog_id.startswith("chromehtml"):
        browser_id, name = "chrome", "Chrome"
        relative_profile = Path("Google") / "Chrome" / "User Data"
    elif prog_id.startswith("msedgehtm"):
        browser_id, name = "edge", "Edge"
        relative_profile = Path("Microsoft") / "Edge" / "User Data"
    else:
        raise RuntimeError("系统默认浏览器不是 Chrome 或 Edge，请改用 Kimi WebBridge 或独立浏览器模式")

    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError(f"无法定位系统默认 {name} 配置目录")
    user_data_dir = Path(local) / relative_profile
    if not user_data_dir.is_dir():
        raise RuntimeError(f"未找到系统默认 {name} 配置目录")
    executable_path = find_system_browser(browser_id)
    if not executable_path:
        raise RuntimeError(f"未找到系统默认 {name} 程序")
    return DefaultBrowserProfile(browser_id, name, executable_path, user_data_dir)


@asynccontextmanager
async def open_default_browser(*, headless: bool = False):
    profile = default_browser_profile()
    playwright = await async_playwright().start()
    context = None
    try:
        try:
            context = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile.user_data_dir),
                executable_path=profile.executable_path,
                headless=headless,
                viewport={"width": 1440, "height": 1000},
                locale="zh-CN",
            )
        except Exception as exc:
            raise RuntimeError(f"无法打开系统默认 {profile.name} 配置。请先关闭所有 {profile.name} 窗口后重试；若仍失败，请改用独立浏览器模式") from exc
        page = context.pages[0] if context.pages else await context.new_page()
        yield BrowserSession(page=page, context=context)
    finally:
        if context:
            await context.close()
        await playwright.stop()
