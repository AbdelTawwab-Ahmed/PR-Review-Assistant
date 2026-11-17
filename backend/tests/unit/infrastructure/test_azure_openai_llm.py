from types import SimpleNamespace

import pytest
from pydantic import BaseModel, SecretStr

from app.application.ports.llm_port import LLMError, ModelTier
from app.infrastructure.llm.azure_openai import AzureOpenAILLM
from app.infrastructure.llm.model_router import ModelRouter
from app.infrastructure.llm.token_tracker import TokenTracker


class Answer(BaseModel):
    text: str


class FakeRunnable:
    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error

    async def ainvoke(self, messages):
        if self.error:
            raise self.error
        return self.result


class FakeChat:
    def __init__(self, runnable: FakeRunnable) -> None:
        self.runnable = runnable

    def with_structured_output(self, schema, include_raw=False):
        return self.runnable


def make_llm(runnable: FakeRunnable) -> tuple[AzureOpenAILLM, TokenTracker]:
    tracker = TokenTracker()
    llm = AzureOpenAILLM(
        endpoint="https://example.openai.azure.com",
        api_key=SecretStr("key"),
        api_version="2025-04-01-preview",
        router=ModelRouter(strong="strong-dep", fast="fast-dep"),
        tracker=tracker,
    )
    llm._models["strong-dep"] = FakeChat(runnable)
    llm._models["fast-dep"] = FakeChat(runnable)
    return llm, tracker


async def test_returns_parsed_output_and_records_usage() -> None:
    raw = SimpleNamespace(usage_metadata={"input_tokens": 10, "output_tokens": 5})
    llm, tracker = make_llm(FakeRunnable({"raw": raw, "parsed": Answer(text="hi")}))
    result = await llm.generate_structured(
        system="s", user="u", schema=Answer, tier=ModelTier.FAST, purpose="reviewer"
    )
    assert result == Answer(text="hi")
    assert tracker.snapshot()["total"] == {"calls": 1, "input_tokens": 10, "output_tokens": 5}


async def test_unparsable_output_raises_llm_error() -> None:
    llm, _ = make_llm(FakeRunnable({"raw": None, "parsed": None}))
    with pytest.raises(LLMError):
        await llm.generate_structured(system="s", user="u", schema=Answer)


async def test_sdk_errors_become_llm_error_without_leaking_details() -> None:
    llm, _ = make_llm(FakeRunnable(error=RuntimeError("secret-endpoint-details")))
    with pytest.raises(LLMError) as exc_info:
        await llm.generate_structured(system="s", user="u", schema=Answer, purpose="security")
    assert "secret-endpoint-details" not in str(exc_info.value)


def test_fast_tier_falls_back_to_strong() -> None:
    assert ModelRouter(strong="big").deployment_for(ModelTier.FAST) == "big"


def test_missing_deployment_raises() -> None:
    with pytest.raises(LLMError):
        ModelRouter(strong="").deployment_for(ModelTier.STRONG)


def test_tracker_aggregates_per_purpose() -> None:
    tracker = TokenTracker()
    tracker.record(purpose="reviewer", input_tokens=10, output_tokens=5)
    tracker.record(purpose="reviewer", input_tokens=1, output_tokens=1)
    snapshot = tracker.snapshot()
    assert snapshot["total"] == {"calls": 2, "input_tokens": 11, "output_tokens": 6}
    assert snapshot["by_purpose"]["reviewer"]["calls"] == 2