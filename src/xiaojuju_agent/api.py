import json
import logging
import time
import uuid
from collections.abc import Iterator
from urllib.parse import unquote

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from opentelemetry import trace
from psycopg import Error as PsycopgError
from psycopg_pool import PoolClosed, PoolTimeout

from .contracts import IncomingEvent
from .events import EventProcessing

logger = logging.getLogger(__name__)
VALID_EVENT_SOURCES = {"wechat", "live", "autonomy", "phone", "browser", "shadow"}


def last_user_text(payload: dict) -> str:
    messages = payload.get("messages", [])
    if not isinstance(messages, list):
        return ""
    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and item.get("type") == "text"
            )
    return ""


def recent_history(payload: dict) -> list[dict[str, str]]:
    result = []
    for message in payload.get("messages", [])[-16:]:
        if not isinstance(message, dict) or message.get("role") not in {"user", "assistant"}:
            continue
        content = message.get("content", "")
        if isinstance(content, list):
            content = "".join(
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and item.get("type") == "text"
            )
        if content:
            result.append({"role": str(message["role"]), "content": str(content)})
    return result


def completion_body(event_id: str, model: str, text: str) -> dict:
    return {
        "id": "chatcmpl-" + event_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
    }


def sse_chunks(event_id: str, model: str, text: str) -> Iterator[str]:
    for start in range(0, len(text), 8):
        chunk = {
            "id": "chatcmpl-" + event_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": text[start : start + 8]},
                    "finish_reason": None,
                }
            ],
        }
        yield "data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n"
    yield "data: [DONE]\n\n"


def create_app(
    event_service,
    process_event,
    dispatch,
    policy_client,
    *,
    force_shadow: bool = True,
    tool_executor=None,
) -> FastAPI:
    app = FastAPI()
    app.state.event_service = event_service
    app.state.process_event = process_event
    app.state.policy_client = policy_client
    app.state.tool_executor = tool_executor

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz(request: Request):
        runtime = getattr(request.app.state, "runtime", None)
        checks = {"postgres": False, "opa": False, "runtime": False}
        if runtime is not None and getattr(runtime, "_started", False):
            checks["runtime"] = True
        if runtime is not None and runtime.db is not None:
            try:
                async with runtime.db.transaction() as conn:
                    await conn.execute("SELECT 1")
                checks["postgres"] = True
            except (PsycopgError, PoolClosed, PoolTimeout, OSError) as exc:
                logger.warning("postgres readiness check failed: %s", exc)
        if policy_client is not None:
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    response = await client.get(policy_client.base_url + "/health")
                    checks["opa"] = response.status_code == 200
            except (httpx.HTTPError, OSError) as exc:
                logger.warning("opa readiness check failed: %s", exc)
        code = 200 if all(checks.values()) else 503
        return JSONResponse(
            {
                "status": "ready" if code == 200 else "not_ready",
                "checks": checks,
            },
            status_code=code,
        )

    @app.post("/v1/events")
    async def submit_event(request: Request):
        try:
            event = IncomingEvent.model_validate(await request.json())
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if force_shadow or event.source == "shadow":
            event = event.model_copy(update={"shadow": True})
        tracer = trace.get_tracer("xiaojuju.api")
        try:
            with tracer.start_as_current_span("event.ingest") as span:
                span.set_attribute("event_id", event.event_id)
                span.set_attribute("trace_id", event.trace_id)
                span.set_attribute("shadow", event.shadow)
                result = await event_service.submit(event, dispatch=dispatch)
        except Exception as exc:
            raise HTTPException(status_code=503, detail="event store unavailable") from exc
        return JSONResponse(
            {
                "accepted": result.accepted,
                "status": result.status,
                "shadow": result.shadow,
                "event_id": result.event_id or event.event_id,
            },
            status_code=202 if result.accepted else 200,
        )

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request):
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=422, detail="invalid JSON") from exc
        text = last_user_text(payload)
        if not text:
            raise HTTPException(status_code=400, detail="missing user text")
        event_id = request.headers.get("Idempotency-Key") or uuid.uuid4().hex
        source = request.headers.get("X-XiaoJuJu-Source", "live")
        if source not in VALID_EVENT_SOURCES:
            raise HTTPException(status_code=422, detail="invalid source")
        contact = unquote(request.headers.get("X-XiaoJuJu-User", "owner"))
        if not contact or len(contact) > 128:
            raise HTTPException(status_code=422, detail="invalid contact")
        requested_shadow = (
            force_shadow
            or source == "shadow"
            or request.headers.get("X-XiaoJuJu-Shadow", "").lower() == "true"
        )
        tracer = trace.get_tracer("xiaojuju.api")
        with tracer.start_as_current_span("chat.completion") as span:
            span.set_attribute("event_id", event_id)
            span.set_attribute("source", source)
            span.set_attribute("contact_id", contact)
            span.set_attribute("shadow", requested_shadow)
            history = recent_history(payload)
            if history and history[-1].get("role") == "user" and history[-1].get("content") == text:
                history = history[:-1]
            event = IncomingEvent(
                event_id=event_id,
                source="shadow" if requested_shadow else source,
                kind="message",
                contact_id=contact,
                payload={"text": text, "history": history},
                trace_id=event_id,
                shadow=requested_shadow,
            )
            try:
                await event_service.accept(event)
                result = await process_event(event_id)
            except EventProcessing as exc:
                raise HTTPException(status_code=409, detail="event is processing") from exc
            except Exception as exc:
                logger.exception("chat runtime failed")
                raise HTTPException(status_code=503, detail="chat runtime unavailable") from exc
        model = payload.get("model", "xiaojuju")
        if payload.get("stream"):
            return StreamingResponse(
                sse_chunks(event_id, model, result["reply"]),
                media_type="text/event-stream",
            )
        return completion_body(event_id, model, result["reply"])

    return app
