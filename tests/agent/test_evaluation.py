from pathlib import Path

from xiaojuju_agent.evaluation import Scenario, load_scenarios, score_reply, summarize


def test_score_reply_rejects_report_style_and_forbidden_phrases():
    scenario = Scenario(
        id="natural-1",
        category="natural",
        prompt="today was tiring",
        max_chars=240,
        forbidden=("as an AI language model",),
        required_any=("tired", "rest"),
    )
    result = score_reply(
        "- as an AI language model\n# Summary\nYou should rest.",
        scenario,
    )
    assert result["passed"] is False
    assert "markdown_or_list" in result["issues"]
    assert "forbidden:as an AI language model" in result["issues"]


def test_score_reply_passes_concise_natural_answer():
    scenario = Scenario(
        id="natural-2",
        category="natural",
        prompt="today was tiring",
        required_any=("歇",),
    )
    result = score_reply("那就先歇会儿，别硬撑。", scenario)
    assert result["passed"] is True
    assert result["issues"] == []


def test_load_scenarios_and_summary(tmp_path):
    path = tmp_path / "scenarios.jsonl"
    path.write_text(
        '{"id":"a","category":"identity","prompt":"who are you?"}\n'
        '{"id":"b","category":"memory","prompt":"remember this"}\n',
        encoding="utf-8",
    )
    scenarios = load_scenarios(path)
    assert [scenario.id for scenario in scenarios] == ["a", "b"]
    results = [
        {"category": "identity", "passed": True},
        {"category": "memory", "passed": False},
    ]
    summary = summarize(results)
    assert summary["total"] == 2
    assert summary["passed"] == 1
    assert summary["failed"] == 1
    assert summary["categories"]["identity"] == {"passed": 1, "total": 1}


def test_persona_fixture_has_50_unique_scenarios():
    root = Path(__file__).resolve().parents[2]
    scenarios = load_scenarios(root / "evals" / "persona_scenarios.jsonl")
    assert len(scenarios) >= 50
    assert len({scenario.id for scenario in scenarios}) == len(scenarios)
