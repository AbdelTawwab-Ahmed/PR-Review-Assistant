import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from typing import Any, TypeVar

from pydantic import BaseModel, SecretStr

from app.application.ports.llm_port import LLMError, ModelTier
from app.infrastructure.llm.model_router import ModelRouter
from app.infrastructure.llm.token_tracker import TokenTracker

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class AzureOpenAILLM:
    def __init__(
        self,
        *,
        endpoint: str,
        api_key: SecretStr,
        api_version: str,
        router: ModelRouter,
        tracker: TokenTracker,
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        max_concurrency: int = 16,
    ) -> None:
        self._endpoint = endpoint
        self._api_key = api_key
        self._api_version = api_version
        self._router = router
        self._tracker = tracker
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._executor = ThreadPoolExecutor(
            max_workers=max_concurrency,
            thread_name_prefix="agent-llm-worker",
        )
        self._models: dict[str, Any] = {}

    def _model(self, deployment: str) -> Any:
        # Built lazily so the app starts even when Azure OpenAI is not configured yet.
        if deployment not in self._models:
            from langchain_openai import AzureChatOpenAI

            self._models[deployment] = AzureChatOpenAI(
                azure_endpoint=self._endpoint,
                api_key=self._api_key,
                api_version=self._api_version,
                azure_deployment=deployment,
                timeout=self._timeout,
                max_retries=self._max_retries,
            )
        return self._models[deployment]

    async def generate_structured(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        tier: ModelTier = ModelTier.STRONG,
        purpose: str = "",
    ) -> T:
        label = purpose or schema.__name__
        deployment = self._router.deployment_for(tier)
        runnable = self._model(deployment).with_structured_output(schema, include_raw=True)
        loop = asyncio.get_running_loop()

        def _execute_in_worker_thread():
            return runnable.invoke([("system", system), ("user", user)])

        async with self._semaphore:
            try:
                # Execute in multi-threaded worker pool to maximize parallelism
                result = await loop.run_in_executor(self._executor, _execute_in_worker_thread)
            except Exception as exc:  # the SDK raises many unrelated error types
                logger.warning("LLM call failed (%s)", label, exc_info=True)
                raise LLMError(f"{label} call failed: {type(exc).__name__}") from exc

        parsed = result.get("parsed")
        if parsed is None:
            raise LLMError(f"{label} returned output that does not match the schema")

        usage = getattr(result.get("raw"), "usage_metadata", None) or {}
        self._tracker.record(
            purpose=label,
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
        )
        return parsed
