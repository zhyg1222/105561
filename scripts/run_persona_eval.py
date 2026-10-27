from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xiaojuju_agent.evaluation import load_scenarios, run_evaluation, summarize


async def run(args) -> dict:
    scenarios = load_scenarios(args.scenarios)
    if args.ids:
        wanted = {item.strip() for item in args.ids.split(",") if item.strip()}
        scenarios = [scenario for scenario in scenarios if scenario.id in wanted]
    if args.limit:
        scenarios = scenarios[: args.limit]
    run_id = time.strftime("%Y%m%d-%H%M%S")

    async with httpx.AsyncClient(timeout=args.timeout) as client:

        async def call(scenario):
            turns = scenario.turns or (scenario.prompt,)
            payload = {
                "model": "xiaojuju",
                "messages": [{"role": "user", "content": text} for text in turns],
            }
            headers = {
                "Idempotency-Key": f"eval:{run_id}:{scenario.id}",
                "X-XiaoJuJu-Source": "live",
                "X-XiaoJuJu-User": f"eval-{run_id}-{scenario.id}",
                "X-XiaoJuJu-Shadow": "false",
            }
            last_error = None
            for attempt in range(3):
                try:
                    response = await client.post(
                        args.api_url.rstrip("/") + "/v1/chat/completions",
                        json=payload,
                        headers=headers,
                    )
                    if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                        await asyncio.sleep(2 * (attempt + 1))
                        continue
                    response.raise_for_status()
                    return response.json()["choices"][0]["message"]["content"]
                except (httpx.HTTPError, TimeoutError) as exc:
                    last_error = exc
                    if attempt >= 2:
                        raise
                    await asyncio.sleep(2 * (attempt + 1))
            raise last_error or RuntimeError("evaluation request failed")

        results = await run_evaluation(scenarios, call)

    summary = summarize(results)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / f"persona-{run_id}.jsonl"
    summary_path = output_dir / f"persona-{run_id}.json"
    with result_path.open("w", encoding="utf-8") as handle:
        for result in results:
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "run_id": run_id,
        "summary": summary,
        "results": str(result_path),
        "summary_path": str(summary_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenarios",
        default=str(ROOT / "evals" / "persona_scenarios.jsonl"),
    )
    parser.add_argument("--api-url", default="http://127.0.0.1:12402")
    parser.add_argument(
        "--output-dir",
        default=r"D:\yige-personal-kb\12_社交代理\小居居\评估",
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--ids", default="")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
