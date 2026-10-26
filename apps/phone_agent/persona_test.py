#!/usr/bin/env python3
import argparse, importlib.util, json, re, time
from pathlib import Path

ROOT = Path(r"D:\yige-personal-kb\12_社交代理\小居居")
PHONE = Path(__file__).resolve().parent / "phone_agent.py"
spec = importlib.util.spec_from_file_location("phone_agent", PHONE)
pa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pa)


def check(case, reply):
    failures = []
    if not reply.strip():
        failures.append("empty_reply")
    if len(reply) > int(case.get("max_chars", 120)):
        failures.append(f"too_long:{len(reply)}")
    if reply.count("?") + reply.count("？") > int(case.get("max_questions", 1)):
        failures.append("too_many_questions")
    if re.search(r"(^|\n)\s*[-*]\s+", reply):
        failures.append("markdown_list")
    must_any = case.get("must_any") or []
    if must_any and not any(x in reply for x in must_any):
        failures.append("missing_any")
    for x in case.get("must_not") or []:
        if x in reply:
            failures.append("forbidden:" + x)
    return failures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--ids", default="")
    args = ap.parse_args()
    cases = json.loads((ROOT / "人格" / "测试用例.json").read_text(encoding="utf-8"))
    if args.quick:
        cases = [c for c in cases if c.get("quick")]
    if args.ids:
        wanted = {x.strip() for x in args.ids.split(",") if x.strip()}
        cases = [c for c in cases if c["id"] in wanted]
    rows = []
    passed = 0
    for case in cases:
        reply = pa.brain(case["input"], [], persist_state=False)
        failures = check(case, reply)
        ok = not failures
        passed += int(ok)
        rows.append({"case": case, "reply": reply, "failures": failures, "pass": ok})
        print(("PASS " if ok else "FAIL ") + case["id"] + ": " + reply)
        if failures:
            print("  " + ", ".join(failures))
    result = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "passed": passed,
        "total": len(cases),
        "rows": rows,
    }
    out = ROOT / "人格" / ("测试结果-" + time.strftime("%Y%m%d-%H%M%S") + ".json")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"RESULT {passed}/{len(cases)} -> {out}")
    raise SystemExit(0 if passed == len(cases) else 1)


if __name__ == "__main__":
    main()