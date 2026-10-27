import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from xiaojuju_core.daemon import tick
from xiaojuju_core.paths import Paths

RUN_LOG = Path(r"D:\yige-personal-kb\.runtime\autonomy")


def record_run(result: dict) -> None:
    RUN_LOG.mkdir(parents=True, exist_ok=True)
    payload = {"generated_at": datetime.now().astimezone().isoformat(), "result": result}
    (RUN_LOG / "last_run.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with (RUN_LOG / "runs.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--pause", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    paths = Paths.production()
    if args.pause:
        paths.paused.parent.mkdir(parents=True, exist_ok=True)
        paths.paused.write_text("paused", encoding="utf-8")
        return
    if args.resume:
        paths.paused.unlink(missing_ok=True)
        return
    if args.status:
        print("paused" if paths.paused.exists() else "running")
        return
    if args.once:
        result = tick(paths, datetime.now(), dry_run=args.dry_run, force=args.force)
        record_run(result)
        print(json.dumps(result, ensure_ascii=False))
        return
    while True:
        result = tick(paths, datetime.now(), dry_run=args.dry_run, force=args.force)
        record_run(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        time.sleep(900)

if __name__ == "__main__":
    main()