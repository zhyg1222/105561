from xiaojuju_agent.journal import (
    meaningful_text,
    render_journal,
    should_include_event,
    should_include_message,
)


def test_journal_filters_test_and_empty_events():
    assert should_include_event("real-event") is True
    assert should_include_event("eval:run:scenario") is False
    assert should_include_event("queue-smoke") is False
    assert should_include_message("real-message") is True
    assert should_include_message("health:20261028") is False
    assert meaningful_text("???") is False
    assert meaningful_text("Introduce yourself as an AI agent") is False
    assert meaningful_text("真实对话") is True


def test_journal_renders_only_real_evidence():
    text = render_journal(
        day="2026-10-28",
        events=[
            {
                "event_id": "real-event",
                "source": "wechat",
                "contact_id": "owner",
                "user_text": "真实问题",
                "reply": "真实回答",
                "created_at": "2026-10-28 09:00:00",
            },
            {
                "event_id": "eval:test",
                "source": "live",
                "contact_id": "owner",
                "user_text": "测试问题",
                "reply": "测试回答",
                "created_at": "2026-10-28 09:01:00",
            },
        ],
        outbox=[
            {"message_id": "real-message", "contact_id": "owner", "status": "sent", "text": "真实发送", "created_at": "2026-10-28 09:02:00"},
            {"message_id": "health:test", "contact_id": "owner", "status": "queued", "text": "告警", "created_at": "2026-10-28 09:03:00"},
        ],
        activities=[{"time": "2026-10-28 09:04:00", "goal": "研究", "status": "done"}],
        health={"ok": True, "checks": {"api": {"ok": True}}},
        memory_stats={"done": 2},
        reflection_text="真实反思",
    )
    assert "真实问题" in text
    assert "测试问题" not in text
    assert "真实发送" in text
    assert "告警" not in text
    assert "真实反思" in text
    assert "健康总状态：正常" in text