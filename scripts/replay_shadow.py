import argparse
import hashlib
import json
import time
from pathlib import Path

import httpx

from xiaojuju_agent.contracts import IncomingEvent


def make_shadow_event(row: dict) -> IncomingEvent:
    canonical = json.dumps(row, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return IncomingEvent(
        event_id="shadow:" + digest,
        source="shadow",
        kind="message",
        contact_id=str(row.get("contact") or "owner"),
        external_id=None,
        payload={"text": str(row.get("user") or "")},
        trace_id="trace:shadow:" + digest[:16],
        shadow=True,
    )


def request_headers(event: IncomingEvent) -> dict[str, str]:
    return {
        "Idempotency-Key": event.event_id,
        "X-XiaoJuJu-Source": "shadow",
        "X-XiaoJuJu-User": event.contact_id or "owner",
        "X-XiaoJuJu-Shadow": "true",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:12400")
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with Path(args.input).open(encoding="utf-8") as src, output.open("w", encoding="utf-8") as dst:
        for line in src:
            if not line.strip():
                continue
            row = json.loads(line)
            event = make_shadow_event(row)
            started = time.perf_counter()
            response = httpx.post(
                args.base_url + "/v1/chat/completions",
                json={
                    "model": "xiaojuju",
                    "messages": [{"role": "user", "content": row.get("user", "")}],
                },
                headers=request_headers(event),
                timeout=120,
            )
            response.raise_for_status()
            body = response.json()
            dst.write(
                json.dumps(
                    {
                        "event_id": event.event_id,
                        "input": row.get("user", ""),
                        "old_reply": row.get("assistant", ""),
                        "reply": body["choices"][0]["message"]["content"],
                        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                        "status": "completed",
                        "trace_id": event.trace_id,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


if __name__ == "__main__":
    main()
