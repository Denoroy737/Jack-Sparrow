"""LLM access for agents (Phase 4).

GroqLLM uses Groq's chat API in JSON mode. Other providers can be added by
implementing `complete_json`. Gemini is the planned fallback (Architecture.md
section 4) and is not wired yet, because no Gemini key has been provided.

`call_agent` owns the retry rule: invalid JSON or a schema mismatch is retried
up to `retries` times with a short correction note, then AgentError is raised.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

log = logging.getLogger("jack_sparrow.llm")

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
GROQ_CHAT_MODEL = "llama-3.3-70b-versatile"  # default; override with JACK_SPARROW_GROQ_CHAT_MODEL

T = TypeVar("T", bound=BaseModel)


NON_RETRYABLE_STATUS = {400, 401, 403, 404, 413, 422}


class LLMError(Exception):
    """The provider call failed. `retryable` is False for errors a retry cannot fix."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.retryable = status not in NON_RETRYABLE_STATUS


class AgentError(Exception):
    """An agent did not return valid output after all retries."""


class LLM(Protocol):
    def complete_json(self, system: str, user: str) -> str: ...


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


class GroqLLM:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = GROQ_CHAT_MODEL,
        client: Any = None,
    ) -> None:
        if client is None:
            from groq import Groq

            client = Groq(api_key=api_key, timeout=90.0, max_retries=2)
        self._client = client
        self._model = model

    def complete_json(self, system: str, user: str) -> str:
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
        except Exception as exc:  # noqa: BLE001 - SDK exception types vary
            status = getattr(exc, "status_code", None)
            raise LLMError(type(exc).__name__, status=status) from exc
        content = resp.choices[0].message.content
        if not content:
            raise LLMError("empty response")
        return content


def call_agent(  # noqa: UP047 - TypeVar keeps Python 3.12 typing simple
    llm: LLM,
    prompt_name: str,
    user_text: str,
    model_cls: type[T],
    *,
    retries: int = 2,
) -> T:
    """Run one agent and return validated output. Raises AgentError when all tries fail."""
    system = load_prompt(prompt_name)
    user = user_text
    last_error = ""
    for attempt in range(retries + 1):
        try:
            raw = llm.complete_json(system, user)
            return model_cls.model_validate_json(raw)
        except (ValidationError, ValueError) as exc:
            last_error = type(exc).__name__
            log.info("agent %s attempt %d invalid output", prompt_name, attempt + 1)
            user = (
                user_text
                + "\n\nYour previous answer was not valid for the required JSON schema. "
                "Return only a valid JSON object."
            )
        except LLMError as exc:
            last_error = str(exc)
            log.info("agent %s attempt %d call failed: %s (status %s)",
                     prompt_name, attempt + 1, last_error, exc.status)
            if not exc.retryable:
                break
    raise AgentError(f"{prompt_name}: {last_error}")
