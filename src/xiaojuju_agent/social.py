from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from .context import current_event_id, current_event_shadow
from .contracts import PolicyInput
from .settings import Settings
from .tools import ToolExecution, ToolExecutor

VERIFY_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "verify_social_post.py"


class SocialPublishRequest(BaseModel):
    platform: str
    account: str
    kind: Literal["note", "video"]
    title: str
    text: str
    media_paths: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    schedule: str | None = None
    event_id: str | None = None
    approval: str | None = None
    shadow: bool = False


@dataclass(frozen=True)
class PublishSpec:
    platform: str
    account: str
    kind: str
    title: str
    text: str
    media_paths: tuple[str, ...]
    tags: tuple[str, ...]
    schedule: str | None
    media_root: Path

    def policy_args(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "account": self.account,
            "kind": self.kind,
            "title": self.title,
            "text": self.text,
            "media_paths": list(self.media_paths),
            "tags": list(self.tags),
            "schedule": self.schedule,
        }


def _clean_tags(tags: list[str] | None) -> tuple[str, ...]:
    cleaned: list[str] = []
    for tag in tags or []:
        value = str(tag).strip().lstrip("#").strip()
        if value and value not in cleaned:
            cleaned.append(value[:40])
    if len(cleaned) > 10:
        raise ValueError("at most 10 tags are allowed")
    return tuple(cleaned)


def _validate_media(paths: list[str], media_root: Path, *, kind: str) -> tuple[str, ...]:
    if not paths:
        raise ValueError("publishing requires at least one media file")
    if kind == "video" and len(paths) != 1:
        raise ValueError("video publishing requires exactly one media file")
    if kind == "note" and len(paths) > 35:
        raise ValueError("note publishing supports at most 35 images")
    root = media_root.resolve()
    values: list[str] = []
    for raw in paths:
        candidate = Path(str(raw)).expanduser().resolve()
        if not candidate.is_file():
            raise ValueError(f"media file does not exist: {raw}")
        if not candidate.is_relative_to(root):
            raise ValueError("media file must be under the configured social media root")
        suffix = candidate.suffix.lower()
        if kind == "video" and suffix not in {".mp4", ".mov", ".mkv", ".webm"}:
            raise ValueError("unsupported video file type")
        if kind == "note" and suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise ValueError("unsupported note image type")
        values.append(str(candidate))
    return tuple(values)


def build_publish_spec(
    request: SocialPublishRequest,
    *,
    media_root: Path,
    identity_label: str,
) -> PublishSpec:
    platform = request.platform.strip().lower()
    if platform not in {"xiaohongshu", "douyin", "tencent"}:
        raise ValueError("unsupported social platform")
    account = request.account.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", account):
        raise ValueError("invalid account name")
    title = request.title.strip()
    if not title or len(title) > 100:
        raise ValueError("title must contain 1-100 characters")
    body = request.text.strip()
    if not body or len(body) > 5000:
        raise ValueError("text must contain 1-5000 characters")
    if identity_label not in body:
        body = f"{identity_label}\n\n{body}"
    schedule = request.schedule.strip() if request.schedule else None
    if schedule and not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", schedule):
        raise ValueError("schedule must use YYYY-MM-DD HH:MM")
    return PublishSpec(
        platform=platform,
        account=account,
        kind=request.kind,
        title=title,
        text=body,
        media_paths=_validate_media(list(request.media_paths), media_root, kind=request.kind),
        tags=_clean_tags(list(request.tags)),
        schedule=schedule,
        media_root=media_root,
    )


class SauCliProvider:
    """Reuse the MIT social-auto-upload CLI without reimplementing selectors."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.home = Path(settings.social_publish_home).resolve()
        self.media_root = Path(settings.social_publish_media_root)
        self.receipts_dir = Path(settings.social_publish_receipts_dir)
        self.identity_label = settings.social_identity_label
        self.timeout = float(settings.social_publish_timeout_seconds)
        self.python = self.home / ".venv" / "Scripts" / "python.exe"
        self.sau = self.home / ".venv" / "Scripts" / "sau.exe"

    def _command_prefix(self) -> list[str]:
        if self.sau.is_file():
            return [str(self.sau)]
        if self.python.is_file():
            return [str(self.python), "-m", "sau_cli"]
        raise RuntimeError("social-auto-upload CLI is not installed")

    def _command(self, spec: PublishSpec) -> list[str]:
        action = "upload-note" if spec.kind == "note" else "upload-video"
        command = [
            *self._command_prefix(),
            spec.platform,
            action,
            "--account",
            spec.account,
            "--title",
            spec.title,
        ]
        if spec.kind == "note":
            command.extend(["--images", *spec.media_paths, "--note", spec.text])
        else:
            command.extend(["--file", spec.media_paths[0], "--desc", spec.text])
        if spec.tags:
            command.extend(["--tags", ",".join(spec.tags)])
        if spec.schedule:
            command.extend(["--schedule", spec.schedule])
        command.append("--headless")
        return command

    async def publish(self, spec: PublishSpec, *, event_id: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._publish_sync, spec, event_id)

    def _publish_sync(self, spec: PublishSpec, event_id: str) -> dict[str, Any]:
        self.receipts_dir.mkdir(parents=True, exist_ok=True)
        temp_dir = self.receipts_dir.parent / "tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        command = self._command(spec)
        env = os.environ.copy()
        env.update(
            {
                "PYTHONIOENCODING": "utf-8",
                "TMP": str(temp_dir),
                "TEMP": str(temp_dir),
            }
        )
        output = ""
        error = ""
        returncode: int | None = None
        status = "failed"
        verification: dict[str, Any] = {
            "verified": False,
            "reason": "cli_not_completed",
        }
        try:
            completed = subprocess.run(
                command,
                cwd=self.home,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
                check=False,
            )
            returncode = completed.returncode
            output = completed.stdout[-8000:]
            error = completed.stderr[-8000:]
            if returncode == 0:
                verification = self._verify_sync(spec, event_id)
                if verification.get("verified"):
                    status = "scheduled" if spec.schedule else "published"
                else:
                    status = "submitted"
        except subprocess.TimeoutExpired as exc:
            status = "submission_unknown"
            verification = {"verified": False, "reason": "cli_timeout"}
            output = str(getattr(exc, "stdout", "") or "")[-8000:]
            error = (str(exc)[-8000:] + "\n" + str(getattr(exc, "stderr", "") or ""))[-8000:]
        except Exception as exc:  # noqa: BLE001 - persist a failed receipt for operators
            error = repr(exc)[-8000:]

        receipt_name = hashlib.sha256(str(event_id).encode("utf-8")).hexdigest()[:24]
        receipt_path = self.receipts_dir / f"{receipt_name}.json"
        receipt = {
            "event_id": str(event_id),
            "platform": spec.platform,
            "account": spec.account,
            "kind": spec.kind,
            "title": spec.title,
            "text": spec.text,
            "media_paths": list(spec.media_paths),
            "tags": list(spec.tags),
            "schedule": spec.schedule,
            "returncode": returncode,
            "stdout": output,
            "stderr": error,
            "status": status,
        }
        receipt["verification"] = verification
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "status": status,
            "verified": bool(verification.get("verified")),
            "verification": verification,
            "receipt_path": str(receipt_path),
            "returncode": returncode,
            "stdout_tail": output,
            "stderr_tail": error,
            "identity_label": self.identity_label,
        }

    def _verify_sync(self, spec: PublishSpec, event_id: str) -> dict[str, Any]:
        if not self.python.is_file() or not VERIFY_SCRIPT.is_file():
            return {"verified": False, "reason": "verifier_unavailable"}
        cookie_file = self.home / "cookies" / f"{spec.platform}_{spec.account}.json"
        digest = hashlib.sha256(str(event_id).encode("utf-8")).hexdigest()[:24]
        screenshot = self.receipts_dir / f"{digest}-verify.png"
        temp_dir = self.receipts_dir.parent / "tmp"
        env = os.environ.copy()
        env.update({"TMP": str(temp_dir), "TEMP": str(temp_dir), "PYTHONIOENCODING": "utf-8"})
        completed = subprocess.run(
            [
                str(self.python),
                str(VERIFY_SCRIPT),
                "--platform",
                spec.platform,
                "--cookie-file",
                str(cookie_file),
                "--title",
                spec.title,
                "--text",
                spec.text,
                "--screenshot",
                str(screenshot),
            ],
            cwd=self.home,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=150,
            check=False,
        )
        lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        if not lines:
            return {
                "verified": False,
                "reason": "verifier_no_output",
                "returncode": completed.returncode,
                "error": completed.stderr[-1000:],
            }
        try:
            result = json.loads(lines[-1])
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass
        return {
            "verified": False,
            "reason": "verifier_invalid_output",
            "returncode": completed.returncode,
            "output": completed.stdout[-1000:],
            "error": completed.stderr[-1000:],
        }

    async def check_session(self, platform: str, account: str) -> dict[str, Any]:
        if platform not in {"xiaohongshu", "douyin", "tencent"}:
            raise ValueError("unsupported social platform")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", account):
            raise ValueError("invalid account name")
        return await asyncio.to_thread(self._check_session_sync, platform, account)

    def _check_session_sync(self, platform: str, account: str) -> dict[str, Any]:
        temp_dir = self.receipts_dir.parent / "tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update({"TMP": str(temp_dir), "TEMP": str(temp_dir), "PYTHONIOENCODING": "utf-8"})
        completed = subprocess.run(
            [*self._command_prefix(), platform, "check", "--account", account],
            cwd=self.home,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
        return {
            "platform": platform,
            "account": account,
            "valid": completed.returncode == 0 and "valid" in completed.stdout.lower(),
            "returncode": completed.returncode,
            "output": completed.stdout[-2000:],
            "error": completed.stderr[-2000:],
        }


class SocialPublishTool:
    def __init__(
        self,
        executor: ToolExecutor,
        provider: SauCliProvider,
        *,
        media_root: Path,
        identity_label: str,
    ):
        self.executor = executor
        self.provider = provider
        self.media_root = media_root
        self.identity_label = identity_label

    async def publish(
        self,
        request: SocialPublishRequest,
        *,
        source: str = "browser",
        event_id: str | None = None,
        approval: str | None = None,
        shadow: bool | None = None,
    ) -> ToolExecution:
        spec = build_publish_spec(
            request,
            media_root=self.media_root,
            identity_label=self.identity_label,
        )
        event_id = event_id or request.event_id or current_event_id() or uuid.uuid4().hex
        if shadow is None:
            shadow = current_event_shadow()
        call = PolicyInput(
            actor="xiaojuju",
            source=source,
            tool="social.publish",
            args=spec.policy_args(),
            event_id=str(event_id),
            risk="external",
            shadow=bool(shadow),
            side_effect=True,
        )
        return await self.executor.execute(
            call,
            lambda: self.provider.publish(spec, event_id=str(event_id)),
            approval=approval or request.approval,
        )

    async def check_session(self, platform: str, account: str) -> dict[str, Any]:
        return await self.provider.check_session(platform, account)


def as_langchain_social_tool(tool: SocialPublishTool) -> StructuredTool:
    async def _publish(
        platform: str,
        account: str,
        kind: str,
        title: str,
        text: str,
        media_paths: list[str],
        tags: list[str] | None = None,
        schedule: str | None = None,
    ) -> str:
        request = SocialPublishRequest(
            platform=platform,
            account=account,
            kind=kind,
            title=title,
            text=text,
            media_paths=media_paths,
            tags=tags or [],
            schedule=schedule,
        )
        execution = await tool.publish(request)
        return json.dumps(
            {
                "executed": execution.executed,
                "decision": execution.decision.model_dump(),
                "result": execution.result,
            },
            ensure_ascii=False,
        )

    return StructuredTool.from_function(
        name="social_publish",
        description=(
            "Publish an AI-labeled note or video to a logged-in Chinese social account. "
            "A side effect always requires explicit one-time approval."
        ),
        coroutine=_publish,
    )