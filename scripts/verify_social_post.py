from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path

from patchright.async_api import async_playwright

URLS = {
    "douyin": [
        "https://creator.douyin.com/creator-micro/content/manage",
        "https://creator.douyin.com/",
    ],
    "xiaohongshu": [
        "https://creator.xiaohongshu.com/creator-micro/content/manage",
        "https://creator.xiaohongshu.com/",
    ],
    "tencent": [
        "https://channels.weixin.qq.com/platform/post/list",
        "https://channels.weixin.qq.com/platform/post/create",
    ],
}
LOGIN_MARKERS = ("扫码登录", "手机号登录", "登录后", "请登录", "scan to login")


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value or "").lower()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True)
    parser.add_argument("--cookie-file", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--text", default="")
    parser.add_argument("--screenshot", required=True)
    return parser.parse_args()


async def verify(args: argparse.Namespace) -> dict:
    cookie_file = Path(args.cookie_file)
    if not cookie_file.is_file():
        return {"verified": False, "reason": "cookie_missing"}
    target_title = compact(args.title)
    target_text = compact(args.text)[:80]
    last_url = ""
    body = ""
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True, channel="chrome")
            context = await browser.new_context(storage_state=str(cookie_file))
            page = await context.new_page()
            try:
                for url in URLS.get(args.platform, []):
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                        await page.wait_for_timeout(4000)
                        last_url = page.url
                        body = await page.locator("body").inner_text(timeout=10000)
                        if any(marker in body for marker in LOGIN_MARKERS):
                            continue
                        normalized = compact(body)
                        if target_title and target_title in normalized:
                            break
                        if target_text and target_text in normalized:
                            break
                    except Exception:  # noqa: BLE001, S112 - try the next platform URL
                        continue
                screenshot = Path(args.screenshot)
                screenshot.parent.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(screenshot), full_page=True)
            finally:
                await context.close()
                await browser.close()
    except Exception as exc:  # noqa: BLE001 - verifier reports failures as data
        return {"verified": False, "reason": "browser_error", "error": repr(exc)}
    normalized = compact(body)
    matched_title = bool(target_title and target_title in normalized)
    matched_text = bool(target_text and target_text in normalized)
    login_required = any(marker in body for marker in LOGIN_MARKERS)
    return {
        "verified": bool((matched_title or matched_text) and not login_required),
        "matched_title": matched_title,
        "matched_text": matched_text,
        "login_required": login_required,
        "url": last_url,
        "screenshot": str(Path(args.screenshot)),
        "reason": "page_text_match" if (matched_title or matched_text) and not login_required
        else "login_required" if login_required else "page_text_not_found",
    }


def main() -> None:
    args = _parse_args()
    print(json.dumps(asyncio.run(verify(args)), ensure_ascii=False))


if __name__ == "__main__":
    main()