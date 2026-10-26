import argparse, json, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from xiaojuju_core.config import load_config
from xiaojuju_core.paths import Paths
from xiaojuju_core.money_brief import build_brief_text, save_brief
from xiaojuju_core.outbox import enqueue_message
from xiaojuju_core.brain import _default_model
from xiaojuju_core.storage import read_json

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--day",default=time.strftime("%Y-%m-%d")); ap.add_argument("--dry-run",action="store_true")
    args=ap.parse_args(); cfg=load_config(); paths=Paths.production(); brief_cfg=cfg["goals"]["daily_brief"]
    if not brief_cfg.get("enabled", False):
        print(json.dumps({"status":"disabled","reason":"daily reports are habits, not constitutional requirements"},ensure_ascii=False)); return
    activity_path=paths.activities/f"{args.day}.jsonl"; rows=[]
    if activity_path.exists():
        for line in activity_path.read_text(encoding="utf-8").splitlines():
            try:
                row=json.loads(line)
                if isinstance(row,dict): rows.append(row)
            except Exception: pass
    queue=read_json(paths.persona/"自主生活"/"兴趣"/"关注队列.json",{"interests":[]})
    topics=[x for x in queue.get("interests",[]) if x.get("status")=="queued"][:brief_cfg.get("max_items",3)]
    text=build_brief_text(rows,topics,model_fn=_default_model)
    path=save_brief(args.day,text,paths.persona/"日报"/"赚钱研究")
    queued=None
    if not args.dry_run:
        queued=enqueue_message(brief_cfg["contact"],text,"money_brief")
    print(json.dumps({"status":"dry_run" if args.dry_run else "queued","brief_path":str(path),"outbox_id":queued.get("id") if queued else None,"text":text},ensure_ascii=False))

if __name__=="__main__":
    main()