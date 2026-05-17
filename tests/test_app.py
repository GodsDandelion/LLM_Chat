from app.main import app


def test_app_metadata() -> None:
    assert app.title == "LLM Chat API"
    assert app.version == "0.1.0"
