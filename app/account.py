from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from app.webbridge import close_managed_pages, ensure_chat, ensure_tab, evaluate


ROOT = Path(os.environ.get("SPARK_ROOT", Path(__file__).resolve().parents[1]))
DATA_DIR = ROOT / "data"
ACCOUNT_PATH = DATA_DIR / "account.json"
AVATAR_PATH = DATA_DIR / "douyin-avatar.jpg"
SCAN_PATH = DATA_DIR / "scan-status.json"


def save_avatar(url: str | None) -> bool:
    if not url:
        return False
    url = urljoin("https://www.douyin.com", url)
    if urlparse(url).scheme != "https":
        return False
    try:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=15) as response:
            content_type = response.headers.get_content_type()
            if content_type not in {"image/jpeg", "image/png", "image/webp"} or urlparse(response.url).scheme != "https":
                return False
            content = response.read(1024 * 1024 + 1)
        if not content or len(content) > 1024 * 1024:
            return False
        temporary = AVATAR_PATH.with_suffix(".tmp")
        temporary.write_bytes(content)
        temporary.replace(AVATAR_PATH)
        return True
    except Exception:
        return False


def refresh_account() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        ensure_chat()
        try:
            previous = json.loads(ACCOUNT_PATH.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError):
            previous = {}
        ensure_tab("https://www.douyin.com/user/self", "火花账号信息")
        profile = evaluate(
            """(async () => {
              const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
              let profile = {name: '', avatar: '', verification: false};
              for (let i = 0; i < 20; i++) {
                const heading = [...document.querySelectorAll('h1')].find(e => e.innerText.trim());
                const image = document.querySelector('[data-e2e="live-avatar"] img') || [...document.images].find(img => heading && img.alt === `${heading.innerText.trim()}头像`);
                profile = {name: heading?.innerText.trim() || '', avatar: image?.currentSrc || image?.src || '', verification: document.title === '验证码中间页'};
                if (profile.verification || (profile.name && profile.avatar)) break;
                await wait(500);
              }
              return profile;
            })()"""
        )
        degraded = not profile.get("name")
        avatar_saved = False if degraded else save_avatar(profile.get("avatar"))
        if degraded:
            name = previous.get("name") or "抖音账号"
            avatar = previous.get("avatar") if AVATAR_PATH.is_file() else None
            avatar = avatar or (AVATAR_PATH.name if AVATAR_PATH.is_file() else None)
        else:
            name = profile["name"]
            avatar = AVATAR_PATH.name if avatar_saved or AVATAR_PATH.is_file() else None
        account = {
            "name": name,
            "avatar": avatar,
            "refreshed_at": datetime.now().astimezone().isoformat(),
        }
        if degraded:
            account["degraded"] = True
        ACCOUNT_PATH.write_text(json.dumps(account, ensure_ascii=False), encoding="utf-8")
        return account
    finally:
        close_managed_pages()


def account_status() -> dict:
    if ACCOUNT_PATH.is_file():
        account = json.loads(ACCOUNT_PATH.read_text(encoding="utf-8"))
    else:
        account = {"name": "", "avatar": None}
    try:
        scan = json.loads(SCAN_PATH.read_text(encoding="utf-8"))
        zone = ZoneInfo("Asia/Shanghai")
        scanned_at = scan.get("scanned_at")
        scanned = datetime.fromisoformat(scanned_at) if scanned_at else datetime.fromtimestamp(SCAN_PATH.stat().st_mtime, zone)
        if scanned.tzinfo is None:
            scanned = scanned.replace(tzinfo=zone)
        if scanned.astimezone(zone).date() != datetime.now(zone).date():
            scan = {"count": None, "targets": [], "stale": True}
    except FileNotFoundError:
        scan = {"count": None, "targets": []}
    except (OSError, TypeError, ValueError):
        scan = {"count": None, "targets": [], "stale": True}
    return {"account": account, "scan": scan}
