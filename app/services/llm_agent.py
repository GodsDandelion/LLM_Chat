from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from app.core.config import Settings, get_settings

# Stop the model from inventing the next user turn in completion-style prompts.
_STOP_SEQUENCES = ["\nUser:", "\n\nUser:", "\nHuman:", "\n\nHuman:", "\n\n\n"]
_DIALOGUE_CUTOFF = re.compile(r"\n(?:User|Human)\s*:", re.IGNORECASE)


def trim_assistant_reply(text: str) -> str:
    """Keep only the assistant's answer; drop fabricated follow-up dialogue."""
    cut = _DIALOGUE_CUTOFF.search(text)
    if cut:
        text = text[: cut.start()]
    return text.strip()


class LLMAgent:
    _instance: "LLMAgent | None" = None
    _llm: object | None = None

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @classmethod
    def get(cls) -> "LLMAgent":
        if cls._instance is None:
            cls._instance = LLMAgent()
        return cls._instance

    def _load_model(self) -> object:
        if self._llm is not None:
            return self._llm
        path = Path(self._settings.llm_model_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(
                f"LLM model not found at {path}. Set LLM_MODEL_PATH or add model.gguf.",
            )
        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise RuntimeError(
                "llama-cpp-python is not installed. Install requirements or set CPU/GPU build per docs.",
            ) from exc

        self._llm = Llama(
            model_path=str(path),
            n_ctx=4096,
            verbose=False,
        )
        return self._llm

    def _build_prompt(self, history: list[tuple[str, str]], user_message: str) -> str:
        parts: list[str] = [
            (
                "You are a helpful assistant. Reply only to the latest user message. "
                "Do not write lines starting with User: or Human:, do not ask yourself "
                "questions, and do not role-play both sides of a conversation.\n"
            ),
        ]
        for role, text in history:
            label = "User" if role == "user" else "Assistant"
            parts.append(f"{label}: {text}\n")
        parts.append(f"User: {user_message}\nAssistant:")
        return "".join(parts)

    def _completion_kwargs(self) -> dict:
        return {
            "max_tokens": self._settings.llm_max_tokens,
            "temperature": self._settings.llm_temperature,
            "stop": _STOP_SEQUENCES,
        }

    def generate(self, history: list[tuple[str, str]], user_message: str) -> str:
        llm = self._load_model()
        prompt = self._build_prompt(history, user_message)
        out = llm(prompt, stream=False, **self._completion_kwargs())
        text = out["choices"][0]["text"]
        return trim_assistant_reply(text) or "."

    def stream_generate(self, history: list[tuple[str, str]], user_message: str) -> Iterator[str]:
        llm = self._load_model()
        prompt = self._build_prompt(history, user_message)
        stream = llm(prompt, stream=True, **self._completion_kwargs())
        buffer = ""
        for chunk in stream:
            delta = chunk["choices"][0].get("text") or ""
            if not delta:
                continue
            buffer += delta
            cut = _DIALOGUE_CUTOFF.search(buffer)
            if cut:
                remainder = buffer[: cut.start()]
                already = len(buffer) - len(delta)
                new_text = remainder[already:]
                if new_text:
                    yield new_text
                return
            yield delta
