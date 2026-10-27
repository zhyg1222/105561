from __future__ import annotations

import re
import time
from collections.abc import Iterable, Sequence
from difflib import SequenceMatcher


def normalize_visible_text(text: str) -> str:
    """Normalize OCR text for conservative on-screen verification."""
    return re.sub(r"[^\u4e00-\u9fff0-9A-Za-z]", "", str(text or ""))


def join_ocr_text(result: Iterable[Sequence], min_score: float = 0.5) -> str:
    parts: list[str] = []
    for item in result or []:
        if len(item) < 3:
            continue
        _box, text, score = item[:3]
        if float(score) >= min_score:
            parts.append(str(text))
    return "".join(parts)


def ocr_contains(result: Iterable[Sequence], expected: str, min_score: float = 0.5) -> bool:
    wanted = normalize_visible_text(expected)
    if not wanted:
        return False
    visible = normalize_visible_text(join_ocr_text(result, min_score))
    if len(wanted) <= 6:
        return wanted in visible
    middle = max(0, (len(wanted) - 6) // 2)
    if any(part in visible for part in (wanted[:6], wanted[middle : middle + 6], wanted[-6:])):
        return True
    # OCR often drops one repeated character or merges adjacent glyphs.
    for start in range(max(1, len(visible) - len(wanted) + 1)):
        for width in range(max(4, len(wanted) - 2), len(wanted) + 3):
            candidate = visible[start : start + width]
            if candidate and SequenceMatcher(None, wanted, candidate).ratio() >= 0.8:
                return True
    return False


def find_ocr_point(
    result: Iterable[Sequence],
    needle: str,
    min_score: float = 0.5,
    *,
    min_y: float | None = None,
    max_y: float | None = None,
) -> tuple[int, int] | None:
    """Return a label centre in original screenshot coordinates."""
    for item in result or []:
        if len(item) < 3:
            continue
        box, text, score = item[:3]
        if float(score) < min_score or needle not in str(text):
            continue
        xs = [float(point[0]) for point in box]
        ys = [float(point[1]) for point in box]
        cy = (min(ys) + max(ys)) / 2
        if min_y is not None and cy < min_y:
            continue
        if max_y is not None and cy > max_y:
            continue
        return int((min(xs) + max(xs)) / 2), int(cy)
    return None


def extract_current_ime(dumpsys_output: str) -> str:
    match = re.search(r"\bmCurMethodId=([^\s]+)", str(dumpsys_output or ""))
    return match.group(1) if match else ""


def pending_left_after_last_right(messages: list[dict]) -> list[dict]:
    """Keep left-side messages that arrived after the latest outgoing bubble."""
    last_right = max(
        (index for index, item in enumerate(messages) if item.get("side") == "right"),
        default=-1,
    )
    return [item for item in messages[last_right + 1 :] if item.get("side") == "left"]


def join_pending_messages(messages: list[dict]) -> str:
    return "\n".join(str(item.get("text", "")) for item in messages if item.get("text"))


def append_history_message(
    history: list[dict], role: str, text: str, at: float | None = None, limit: int = 20
) -> list[dict]:
    history.append({"role": role, "text": text, "at": time.time() if at is None else at})
    del history[: -max(1, limit)]
    return history
