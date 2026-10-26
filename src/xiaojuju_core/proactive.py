import json, re
from datetime import datetime, time as dtime

def _clock(value):
    h,m=str(value).split(":",1); return dtime(int(h),int(m))

def can_send(now: datetime, state: dict, cfg: dict, last_user_at=None, last_sent_at=None, daily_count=0, pending=0):
    if not cfg.get("enabled", False):
        return False, "disabled"
    start,end=(_clock(x) for x in cfg["allowed_hours"])
    if not (start <= now.time() < end):
        return False, "outside_hours"
    if pending > 0:
        return False, "pending_message"
    if daily_count >= int(cfg.get("max_per_day",2)):
        return False, "daily_limit"
    if last_sent_at:
        if now - last_sent_at < __import__("datetime").timedelta(hours=float(cfg.get("min_hours_between",3))):
            return False, "recent_proactive_chat"
    if last_user_at:
        if now - last_user_at < __import__("datetime").timedelta(minutes=float(cfg.get("min_minutes_after_user_message",120))):
            return False, "recent_user_chat"
    return True, "ok"

def parse_proactive(raw: str) -> dict:
    text=re.sub(r"^```(?:json)?\s*|\s*```$","",(raw or "").strip(),flags=re.I)
    match=re.search(r"\{.*\}",text,re.S)
    if not match:
        return {"should_send":False,"message":"","reason":"invalid_json"}
    try: data=json.loads(match.group(0))
    except Exception: return {"should_send":False,"message":"","reason":"invalid_json"}
    msg=re.sub(r"[#*`>]+","",str(data.get("message",""))).strip()
    msg=re.sub(r"\s+"," ",msg)
    bad=any(x in msg for x in ("今日报告","研究简报","首先","其次","总结如下"))
    if not data.get("should_send") or not msg or len(msg)>120 or bad or msg.startswith(("- ","1. ")):
        return {"should_send":False,"message":"","reason":"not_casual_or_too_long"}
    return {"should_send":True,"message":msg,"reason":str(data.get("reason",""))[:80]}

def build_proactive_prompt(constitution: str, live_persona: str, context: dict) -> tuple[str,str]:
    system=constitution+"\n\n"+live_persona+"\n\n"+"你现在要判断是否主动给老大发一条微信。只有存在自然、真实的理由才发：分享一个刚看到/刚想到的东西、关心近况、接续旧话题、或者单纯想聊两句。不要为了刷存在感，不要汇报工作，不要列清单，不要编造现实经历。宁可不发。只输出 JSON：{\"should_send\":true/false,\"message\":\"1到2句，15到60个汉字\",\"reason\":\"为什么现在想发\"}。"
    user=json.dumps(context,ensure_ascii=False)
    return system,user