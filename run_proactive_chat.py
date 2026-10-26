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
from xiaojuju_core.storage import atomic_write_json, read_json

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--dry-run",action="store_true"); args=ap.parse_args()
    cfg=load_config(); habits=cfg["habits"]; pc=habits["proactive_chat"]; paths=Paths.production()
    state_path=paths.persona/"社交"/"主动聊天状态.json"; state=read_json(state_path,{"day":"","count":0,"last_sent_epoch":0})
    today=time.strftime("%Y-%m-%d")
    if state.get("day")!=today: state={"day":today,"count":0,"last_sent_epoch":0}
    mem_path=paths.memory_events; recent=[]; last_user_at=None
    if mem_path.exists():
        for line in mem_path.read_text(encoding="utf-8").splitlines()[-8:]:
            try:
                row=json.loads(line); recent.append({"user":row.get("user",""),"assistant":row.get("assistant","")})
                if row.get("epoch"): last_user_at=datetime.fromtimestamp(float(row["epoch"]))
            except Exception: pass
    last_sent_at=datetime.fromtimestamp(float(state.get("last_sent_epoch",0))) if state.get("last_sent_epoch") else None
    ok,reason=can_send(datetime.now(),state,pc,last_user_at,last_sent_at,int(state.get("count",0)),len(pending_messages()))
    if not ok:
        print(json.dumps({"status":"skipped","reason":reason},ensure_ascii=False)); return
    queue=read_json(paths.persona/"自主生活"/"兴趣"/"关注队列.json",{"interests":[]})
    interests=[x.get("topic") for x in queue.get("interests",[]) if x.get("status")=="queued"][:3]
    activity_path=paths.activities/f"{today}.jsonl"; activities=[]
    if activity_path.exists():
        for line in activity_path.read_text(encoding="utf-8").splitlines()[-5:]:
            try: activities.append(json.loads(line).get("goal",""))
            except Exception: pass
    constitution=(paths.persona/"人格宪法.md").read_text(encoding="utf-8")
    live=(Path(__file__).resolve().parent/"prompts"/"live_persona.md").read_text(encoding="utf-8")
    context={"now":datetime.now().strftime("%Y-%m-%d %H:%M"),"state":read_json(paths.state,{}),"recent_chat":recent,"interests":interests,"today_activities":activities}
    system,user=build_proactive_prompt(constitution,live,context)
    decision=parse_proactive(_default_model(system,user,max_tokens=100))
    if not decision.get("should_send"):
        print(json.dumps({"status":"skipped","reason":decision.get("reason","no_natural_reason")},ensure_ascii=False)); return
    message=decision["message"]
    if args.dry_run:
        print(json.dumps({"status":"dry_run","message":message,"reason":decision.get("reason","")},ensure_ascii=False)); return
    queued=enqueue_message(pc["contact"],message,"proactive_chat")
    state["count"]=int(state.get("count",0))+1; state["last_sent_epoch"]=time.time()
    atomic_write_json(state_path,state)
    print(json.dumps({"status":"queued","message":message,"outbox_id":queued["id"]},ensure_ascii=False))

if __name__=="__main__": main()