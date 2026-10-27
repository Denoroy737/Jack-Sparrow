import pytest

from app.llm import AgentError, LLMError, call_agent
from app.schemas import Classification


class Scripted:
    def __init__(self, errors):
        self.errors = list(errors)
        self.calls = 0

    def complete_json(self, system, user):
        self.calls += 1
        raise self.errors.pop(0)


def test_404_is_not_retried() -> None:
    llm = Scripted([LLMError("NotFoundError", status=404)] * 3)
    with pytest.raises(AgentError):
        call_agent(llm, "classifier", "x", Classification)
    assert llm.calls == 1


def test_rate_limit_is_retried() -> None:
    err = LLMError("RateLimitError", status=429)
    assert err.retryable is True
    class Mixed:
        def __init__(self):
            self.calls = 0

        def complete_json(self, system, user):
            self.calls += 1
            if self.calls < 3:
                raise LLMError("RateLimitError", status=429)
            return '{"category": "coding", "tags": [], "confidence": "high"}'

    m = Mixed()
    result = call_agent(m, "classifier", "x", Classification)
    assert result.category == "coding" and m.calls == 3


def test_404_error_marked_non_retryable() -> None:
    assert LLMError("x", status=404).retryable is False
    assert LLMError("x", status=500).retryable is True
    assert LLMError("x").retryable is True
