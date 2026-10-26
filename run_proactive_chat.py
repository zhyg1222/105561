import argparse, json, sys, time
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from xiaojuju_core.config import load_config
from xiaojuju_core.paths import Paths
from xiaojuju_core.proactive import can_send, parse_proactive, build_proactive_prompt
from xiaojuju_core.outbox import enqueue_message, pending_messages
from xiaojuju_core.brain import _default_model
from xiaojuju_core.event_bus import EventBus
from xiaojuju_core.memory_db import MemoryStore
from xiaojuju_core.storage import atomic_write_json, read_json

def _check(paths, pc, dry_run, event_id):
    state_path=paths.persona/"\u793e\u4ea4"/"\u4e3b\u52a8\u804a\u5929\u72b6\u6001.json"
    state=read_json(state_path,{"day":"","count":0,"last_sent_epoch":0})
    today=time.strftime("%Y-%m-%d")
    if state.get("day")!=today:
        state={"day":today,"count":0,"last_sent_epoch":0}
    with MemoryStore(paths.memory_db) as store:
        store.migrate_jsonl(paths.memory_events)
        rows=store.retrieve(pc["contact"], "", limit=8)
    recent=[{"user":row.get("user",""),"assistant":row.get("assistant","")} for row in rows]
    epochs=[float(row.get("epoch",0)) for row in rows if row.get("epoch")]
    last_user_at=datetime.fromtimestamp(max(epochs)) if epochs else None
    last_sent_at=datetime.fromtimestamp(float(state.get("last_sent_epoch",0))) if state.get("last_sent_epoch") else None
    ok,reason=can_send(datetime.now(),state,pc,last_user_at,last_sent_at,int(state.get("count",0)),len(pending_messages()))
    if not ok:
        return {"status":"skipped","reason":reason}
    queue=read_json(paths.persona/"\u81ea\u4e3b\u751f\u6d3b"/"\u5174\u8da3"/"\u5173\u6ce8\u961f\u5217.json",{"interests":[]})
    interests=[x.get("topic") for x in queue.get("interests",[]) if x.get("status")=="queued"][:3]
    activity_path=paths.activities/f"{today}.jsonl"; activities=[]
    if activity_path.exists():
        for line in activity_path.read_text(encoding="utf-8").splitlines()[-5:]:
            try: activities.append(json.loads(line).get("goal",""))
            except Exception: pass
    constitution=(paths.persona/"\u4eba\u683c\u5baa\u6cd5.md").read_text(encoding="utf-8")
    live=(Path(__file__).resolve().parent/"prompts"/"live_persona.md").read_text(encoding="utf-8")
    context={"now":datetime.now().strftime("%Y-%m-%d %H:%M"),"state":read_json(paths.state,{}),"recent_chat":recent,"interests":interests,"today_activities":activities}
    system,user=build_proactive_prompt(constitution,live,context)
    decision=parse_proactive(_default_model(system,user,max_tokens=100))
    if not decision.get("should_send"):
        return {"status":"skipped","reason":decision.get("reason","no_natural_reason")}
    message=decision["message"]
    if dry_run:
        return {"status":"dry_run","message":message,"reason":decision.get("reason","")}
    queued=enqueue_message(pc["contact"],message,"proactive_chat",message_id=event_id)
    state["count"]=int(state.get("count",0))+1
    state["last_sent_epoch"]=time.time()
    atomic_write_json(state_path,state)
    return {"status":"queued","message":message,"outbox_id":queued["id"]}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--dry-run",action="store_true"); args=ap.parse_args()
    cfg=load_config(); pc=cfg["habits"]["proactive_chat"]; paths=Paths.production()
    now=datetime.now(); hour=now.strftime("%Y-%m-%dT%H")
    event_id=f"proactive:{hour}" + (":dry-run" if args.dry_run else "")
    with EventBus(paths.event_bus) as bus:
        bus.enqueue(event_id,"proactive_chat",{"hour":hour,"dry_run":args.dry_run},priority=30)
        existing=bus.get(event_id)
        if existing and existing.get("status")=="completed":
            print(json.dumps({"status":"skipped","reason":"already_checked","event_id":event_id},ensure_ascii=False)); return
        claimed=bus.claim(event_id)
        if claimed is None:
            print(json.dumps({"status":"skipped","reason":"event_busy","event_id":event_id},ensure_ascii=False)); return
        try:
            result=_check(paths,pc,args.dry_run,event_id)
        except Exception as exc:
            bus.fail(event_id,repr(exc),retry=True)
            raise
        result["event_id"]=event_id
        bus.complete(event_id,result)
    print(json.dumps(result,ensure_ascii=False))

if __name__=="__main__": main()
