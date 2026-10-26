import json
import time
import uuid
from collections.abc import Iterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse

from .contracts import IncomingEvent


def last_user_text(payload: dict) -> str:
    for message in reversed(payload.get("messages", [])):
        if message.get("role") != "user":
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


def create_app(event_service, graph, dispatch, policy_client) -> FastAPI:
    app = FastAPI()
    app.state.event_service = event_service
    app.state.graph = graph
    app.state.policy_client = policy_client

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.post("/v1/events")
    async def submit_event(request: Request):
        try:
            event = IncomingEvent.model_validate(await request.json())
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        try:
            result = await event_service.submit(event, dispatch=dispatch)
        except Exception as exc:
            raise HTTPException(status_code=503, detail="event store unavailable") from exc
        return {
            "accepted": result.accepted,
            "status": result.status,
            "shadow": result.shadow,
        }

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request):
        payload = await request.json()
        text = last_user_text(payload)
        if not text:
            raise HTTPException(status_code=400, detail="missing user text")
        event_id = request.headers.get("Idempotency-Key") or uuid.uuid4().hex
        source = request.headers.get("X-XiaoJuJu-Source", "live")
        contact = request.headers.get("X-XiaoJuJu-User", "owner")
        result = await graph.ainvoke(
            {"user_text": text, "messages": [], "trace_id": event_id},
            {"configurable": {"thread_id": f"{source}:{contact}"}},
        )
        model = payload.get("model", "xiaojuju")
        if payload.get("stream"):
            return StreamingResponse(
                sse_chunks(event_id, model, result["reply"]),
                media_type="text/event-stream",
            )
        return completion_body(event_id, model, result["reply"])

    return app
