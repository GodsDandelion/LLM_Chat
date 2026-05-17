from app.services.llm_agent import trim_assistant_reply


def test_trim_assistant_reply_stops_at_fake_user_turn() -> None:
    raw = "Here is the answer.\n\nUser: What about X?\nAssistant: More text."
    assert trim_assistant_reply(raw) == "Here is the answer."


def test_trim_assistant_reply_keeps_single_block() -> None:
    assert trim_assistant_reply("  Hello world  ") == "Hello world"
