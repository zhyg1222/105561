import tempfile, unittest
from pathlib import Path
from xiaojuju_core.activity import run_activity


class ActivityTests(unittest.TestCase):
    def test_runner_output_is_saved(self):
        def fake_runner(prompt):
            return {"title": "人类为什么爱看直播", "markdown": "# 观察\n\n人看直播是在找陪伴。"}

        with tempfile.TemporaryDirectory() as d:
            out = run_activity(
                {"title": "自由研究", "source": "self"},
                {"mood": "松弛"},
                "2026-10-26 10:00:00",
                fake_runner,
                Path(d),
            )
            self.assertEqual(out["status"], "done")
            self.assertEqual(len(list(Path(d).glob("*.md"))), 1)

    def test_empty_output_fails(self):
        with tempfile.TemporaryDirectory() as d:
            out = run_activity(
                {"title": "自由研究"}, {}, "2026-10-26 10:00:00", lambda p: {}, Path(d)
            )
            self.assertEqual(out["status"], "failed")

    def test_web_events_are_written_to_audit(self):
        import json
        from xiaojuju_core.activity import audit_web_events

        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "web.jsonl"
            stdout = "\n".join(
                [
                    json.dumps(
                        {
                            "type": "tool_call",
                            "callId": "c1",
                            "tool": "web_search",
                            "input": {"queries": ["测试"]},
                        },
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        {"type": "tool_result", "callId": "c1", "status": "completed"},
                        ensure_ascii=False,
                    ),
                ]
            )
            audit_web_events(stdout, p)
            rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(rows[0]["action"], "web_search")
            self.assertEqual(rows[-1]["result"], "completed")

    def test_specific_goal_retries_off_goal_output(self):
        calls = []

        def fake_runner(prompt):
            calls.append(prompt)
            if len(calls) == 1:
                return {"title": "章鱼为什么是蓝血", "markdown": "和当前目标无关的内容"}
            return {"title": "微信和抖音内容转化收入", "markdown": "围绕微信、抖音内容和收入的路径"}

        with tempfile.TemporaryDirectory() as d:
            goal = {
                "title": "研究：微信和抖音内容如何转化为收入",
                "detail": "内容、直播、私域与交易",
                "source": "self",
            }
            out = run_activity(goal, {}, "2026-10-26 10:00:00", fake_runner, Path(d))
            self.assertEqual(out["status"], "done")
            self.assertEqual(len(calls), 2)

    def test_specific_goal_fails_after_repeated_off_goal_output(self):
        with tempfile.TemporaryDirectory() as d:
            goal = {"title": "研究：微信和抖音内容如何转化为收入", "source": "self"}
            out = run_activity(
                goal,
                {},
                "2026-10-26 10:00:00",
                lambda p: {"title": "章鱼", "markdown": "猫"},
                Path(d),
            )
            self.assertEqual(out["status"], "failed")
            self.assertEqual(out["error"], "off_goal")
