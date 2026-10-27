from xiaojuju_agent.style import clean_chat_reply


def test_clean_chat_reply_removes_report_format_and_keeps_two_sentences():
    raw = "# 标题\n- 第一句。第二句！第三句？"
    assert clean_chat_reply(raw) == "标题 第一句。第二句！"


def test_clean_chat_reply_caps_long_output():
    raw = "这是一个很长的回答" * 30
    result = clean_chat_reply(raw, max_chars=40)
    assert len(result) <= 40
    assert result
