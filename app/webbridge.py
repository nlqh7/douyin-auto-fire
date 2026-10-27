from __future__ import annotations

import json
import time
from urllib.request import Request, urlopen


BRIDGE_URL = "http://127.0.0.1:10086/command"
SESSION = "spark-keeper-v2"
CHAT_URL = "https://www.douyin.com/chat"


class WebBridgeError(RuntimeError):
    pass


def _post(action: str, args: dict, timeout: float = 45) -> dict:
    body = json.dumps({"action": action, "args": args, "session": SESSION}, ensure_ascii=False).encode("utf-8")
    request = Request(BRIDGE_URL, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise WebBridgeError("无法连接 Kimi WebBridge，请确认扩展和本机服务已开启") from exc


def connection_status() -> dict:
    """快速探测本机桥接服务，不创建标签页，也不影响正常扫描的长超时。"""
    try:
        payload = _post("list_tabs", {}, timeout=2)
    except WebBridgeError as exc:
        return {"available": False, "message": str(exc)}
    if payload.get("ok"):
        return {"available": True}
    return {"available": False, "message": "Kimi WebBridge 未就绪，请确认扩展和本机服务已开启"}


def command(action: str, args: dict | None = None, _retries: int = 0) -> dict:
    payload = _post(action, args or {})
    if not payload.get("ok"):
        error = payload.get("error") or payload
        message = str(error.get("message", error) if isinstance(error, dict) else error)
        normalized = message.lower()
        recoverable = "detached" in normalized or "no tab with given id" in normalized
        if recoverable and _retries < 2:
            time.sleep(0.5)
            return command(action, args, _retries + 1)
        raise WebBridgeError(message)
    data = payload.get("data")
    return data if isinstance(data, dict) else {"value": data}


def evaluate(code: str):
    result = command("evaluate", {"code": code})
    return result.get("value")


def ensure_tab(url: str, group_title: str) -> None:
    tabs = command("list_tabs").get("tabs", [])
    existing = next((tab for tab in tabs if tab.get("url", "").startswith(url)), None)
    if existing:
        command("find_tab", {"url": existing.get("url") or url})
    else:
        command("navigate", {"url": url, "newTab": True, "group_title": group_title})


def ensure_chat() -> None:
    ensure_tab(CHAT_URL, "火花管家")
    for attempt in range(2):
        time.sleep(3)
        evaluate("(() => { const cancel = document.querySelector('[class*=\"searchSearchInputsearch_cancel\"]'); if (cancel && cancel.offsetParent !== null) { cancel.click(); return true; } return false; })()")
        time.sleep(0.5)
        structure = evaluate(
            "(() => ({login: document.body.innerText.includes('扫码登录'), search: document.querySelectorAll('input[placeholder*=\"搜索\"]').length}))()"
        )
        if structure.get("login"):
            raise WebBridgeError("当前抖音页面需要登录，请在已打开的 Chrome 页面登录后重试")
        if structure.get("search"):
            return
        if attempt == 0:
            evaluate("(() => { location.reload(); return true; })()")
    raise WebBridgeError("抖音私信页刷新后仍未就绪或页面结构已变化")


def close_managed_pages() -> None:
    command("close_session")


def discover_gray_streaks() -> list[str]:
    result = evaluate(
        """(async () => {
          const list = [...document.querySelectorAll('[class*="conversationConversationListwrapper"]')].find(e => e.getBoundingClientRect().height > 0);
          if (!list) return {conversations: 0, names: []};
          const conversations = document.querySelectorAll('[data-e2e="conversation-item"]').length;
          const names = new Set();
          list.scrollTop = 0;
          const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
          await wait(400);
          for (let i = 0; i < 100; i++) {
            list.querySelectorAll('[data-e2e="conversation-item"]:has([class*="commonStreakstreakContainer"] [class*="commonStreakicon"][src*="/gray_"])').forEach(row => {
              const title = row.querySelector('[class*="conversationConversationItemtitle"]');
              const name = title && (title.innerText || title.textContent || '').split('\\n')[0].trim();
              if (name) names.add(name);
            });
            if (list.scrollTop + list.clientHeight >= list.scrollHeight - 2) break;
            list.scrollTop = Math.min(list.scrollTop + Math.max(300, list.clientHeight * .8), list.scrollHeight);
            await wait(350);
          }
          return {conversations, names: [...names]};
        })()"""
    )
    if not result.get("conversations"):
        raise WebBridgeError("未识别到私信会话，无法确认扫描是否有效")
    return result["names"]


def trusted_click(rect: dict) -> None:
    x, y = rect["x"], rect["y"]
    command("cdp", {"method": "Input.dispatchMouseEvent", "params": {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1}})
    command("cdp", {"method": "Input.dispatchMouseEvent", "params": {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1}})


def open_target(name: str) -> None:
    encoded = json.dumps(name, ensure_ascii=False)
    rect = None
    for attempt in range(3):
        rect = evaluate(
        f"""(async () => {{
          const expected = {encoded};
          const list = [...document.querySelectorAll('[class*="conversationConversationListwrapper"]')].find(e => e.getBoundingClientRect().height > 0);
          if (!list) return {{reason: 'no-list'}};
          let matches = 0;
          const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
          list.scrollTop = 0;
          await wait(1200);
          for (let i = 0; i < 100; i++) {{
            for (const row of list.querySelectorAll('[data-e2e="conversation-item"]')) {{
              const title = row.querySelector('[class*="conversationConversationItemtitle"]');
              if (title && (title.innerText || title.textContent || '').split('\\n')[0].trim() === expected) {{
                matches += 1;
                list.scrollTop = Math.max(0, row.offsetTop - list.clientHeight / 2);
                await wait(400);
                const bounds = row.getBoundingClientRect();
                if (bounds.width > 0 && bounds.height > 0) return {{x: bounds.x + bounds.width / 2, y: bounds.y + bounds.height / 2}};
              }}
            }}
            if (list.scrollTop + list.clientHeight >= list.scrollHeight - 2) break;
            list.scrollTop = Math.min(list.scrollTop + Math.max(300, list.clientHeight * .8), list.scrollHeight);
            await wait(250);
          }}
          return {{reason: 'not-visible', matches}};
        }})()"""
        )
        if rect and "x" in rect:
            break
        time.sleep(0.5)
    if not rect or "x" not in rect:
        raise WebBridgeError(f"无法定位目标会话（名称匹配数: {rect.get('matches', 0) if rect else 0}）")
    trusted_click(rect)
    deadline = time.monotonic() + 10
    confirmed = {}
    while True:
        confirmed = evaluate(
            f"""(() => {{
              const header = document.querySelector('[class*="RightPanelHeadertitle"]');
              const title = (header?.innerText || header?.textContent || '').split('\\n')[0].trim();
              const composer = document.querySelector('[data-contents="true"], [contenteditable="true"], textarea[placeholder*="消息"]');
              const bounds = composer?.getBoundingClientRect();
              return {{title, composer: Boolean(bounds && bounds.width > 0 && bounds.height > 0)}};
            }})()"""
        ) or {}
        if confirmed.get("title") == name and confirmed.get("composer"):
            return
        if time.monotonic() >= deadline:
            break
        time.sleep(0.4)
    if confirmed.get("title") != name:
        raise WebBridgeError("无法确认目标会话：右侧标题与精确名称不一致")
    if not confirmed.get("composer"):
        raise WebBridgeError("无法确认目标会话：右侧输入框不可用")


def _message_anchor() -> str:
    result = evaluate(
        """(() => {
          const latest = document.querySelector('.messageMessageListlist [data-index="0"] .messageMessageBoxmessageBox:has(.messageMessageBoxcontentBox.messageMessageBoxisFromMe)');
          const anchor = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
          if (latest) latest.setAttribute('data-spark-send-anchor', anchor);
          return {anchor};
        })()"""
    )
    return result["anchor"]


def _click_publish() -> None:
    rect = evaluate(
        "(() => { const button = [...document.querySelectorAll('[class*=\"messageMsgInputpublishBtn\"], .e2e-send-msg-bt, button[aria-label*=\"发送\"]')].find(e => !e.disabled && e.getBoundingClientRect().width > 0 && e.getBoundingClientRect().height > 0); if (!button) return null; const bounds = button.getBoundingClientRect(); return {x: bounds.x + bounds.width / 2, y: bounds.y + bounds.height / 2}; })()"
    )
    if not rect:
        raise WebBridgeError("找不到发送按钮")
    trusted_click(rect)


def _confirm_message(anchor: str, *, text: str = "", resource: str = "", sticker: str = "") -> None:
    values = json.dumps({"anchor": anchor, "text": text, "resource": resource, "sticker": sticker}, ensure_ascii=False)
    result = evaluate(
        f"""(async () => {{
          const expected = {values};
          const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
          const deadline = Date.now() + 12000;
          const normalize = value => (value || '').replace(/[\\s\\u200B\\u200C\\u200D\\uFEFF]+/g, ' ').trim();
          const label = value => normalize(value).replace(/^[\\[【]|[\\]】]$/g, '');
          const path = value => {{ try {{ return new URL(value, location.href).pathname; }} catch {{ return value; }} }};
          let stableSince = null;
          while (Date.now() < deadline) {{
            const latest = document.querySelector('.messageMessageListlist [data-index="0"] .messageMessageBoxmessageBox:has(.messageMessageBoxcontentBox.messageMessageBoxisFromMe)');
            if (!latest || latest.getAttribute('data-spark-send-anchor') === expected.anchor) {{
              await wait(250);
              continue;
            }}
            const content = latest.querySelector('[data-e2e="msg-item-content"]') || latest;
            const failed = latest.querySelector('[aria-label*="重试"], [title*="重试"], [class*="sendFailed"], [class*="SendFailed"], [class*="SendStatusretry"], [class*="ContentSideSendStatusretry"]');
            if (failed) return {{status: 'failed'}};
            const images = [...content.querySelectorAll('img')];
            const stickerBubble = content.querySelector('.MessageItemEmojiemojiBox img, .MessageItemEmojiimage');
            const resourceMatches = !expected.resource || Boolean(stickerBubble) || images.some(image => path(image.currentSrc || image.src) === path(expected.resource));
            const stickerMatches = !expected.sticker || Boolean(stickerBubble) || images.some(image => label(image.getAttribute('aria-label') || image.title || image.alt) === expected.sticker);
            const textMatches = !expected.text || normalize(content.innerText).includes(normalize(expected.text));
            if (!resourceMatches || !stickerMatches || !textMatches) {{
              stableSince = null;
              await wait(250);
              continue;
            }}
            const pending = latest.querySelector('.semi-spin, [class*="im-saas-message-spin"], [data-icon="spin"]');
            if (pending) {{
              stableSince = null;
            }} else {{
              stableSince ??= Date.now();
              if (Date.now() - stableSince >= 1000) return {{status: 'sent'}};
            }}
            await wait(250);
          }}
          return {{status: 'unknown'}};
        }})()"""
    )
    if result.get("status") == "failed":
        raise WebBridgeError("页面显示发送失败，不会重试")
    if result.get("status") != "sent":
        raise WebBridgeError("无法确认本次新增消息及内容，为避免重复不会重试")


def send_text(content: str) -> None:
    anchor = _message_anchor()
    command("fill", {"selector": '[data-contents="true"]', "value": content})
    _click_publish()
    _confirm_message(anchor, text=content)


def send_sticker(name: str) -> None:
    anchor = _message_anchor()
    rect = evaluate(
        "(() => { const button = [...document.querySelectorAll('svg.messageMsgInputiconAction, button[aria-label*=\"表情\"], [role=\"button\"][aria-label*=\"表情\"]')].find(e => e.getBoundingClientRect().width > 0 && e.getBoundingClientRect().height > 0); if (!button) return null; const bounds = button.getBoundingClientRect(); return {x: bounds.x + bounds.width / 2, y: bounds.y + bounds.height / 2}; })()"
    )
    if not rect:
        raise WebBridgeError("找不到表情按钮")
    trusted_click(rect)
    time.sleep(0.8)
    encoded = json.dumps(name, ensure_ascii=False)
    selected = evaluate(
        f"""(() => {{
          const panels = [...document.querySelectorAll('.componentsemojiemojiPanel, [class*="emojiPanel"], [role="dialog"]')];
          for (const panel of panels) {{
            for (const node of panel.querySelectorAll('[aria-label], [title], img, .emojiEmojiItememojiItemDesc')) {{
              const label = node.getAttribute('aria-label') || node.getAttribute('title') || node.getAttribute('alt') || node.innerText;
              if (label?.trim() === {encoded}) {{
                const target = node.closest('.emojiEmojiItememojiItem')?.querySelector('.emojiEmojiItemimgBox') || node.closest('[role="button"]') || node;
                const image = target.matches('img') ? target : target.querySelector('img');
                const bounds = target.getBoundingClientRect();
                return {{x: bounds.x + bounds.width / 2, y: bounds.y + bounds.height / 2, resource: image?.currentSrc || image?.src || ''}};
              }}
            }}
          }}
          return null;
        }})()"""
    )
    if not selected:
        raise WebBridgeError(f"表情面板中找不到原生表情：{name}")
    trusted_click(selected)
    time.sleep(1)
    publish = evaluate(
        "(() => { const button = document.querySelector('[class*=\"messageMsgInputpublishBtn\"], .e2e-send-msg-bt'); if (!button) return null; const bounds = button.getBoundingClientRect(); return {x: bounds.x + bounds.width / 2, y: bounds.y + bounds.height / 2}; })()"
    )
    if not publish:
        raise WebBridgeError("找不到发送按钮")
    trusted_click(publish)
    _confirm_message(anchor, resource=selected["resource"], sticker=name)
