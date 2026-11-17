from app.application.ports.llm_port import LLMError, ModelTier


class ModelRouter:
    """Maps a model tier to an Azure OpenAI deployment name. FAST falls back to STRONG."""

    def __init__(self, strong: str, fast: str = "") -> None:
        self._deployments = {ModelTier.STRONG: strong, ModelTier.FAST: fast or strong}

    def deployment_for(self, tier: ModelTier) -> str:
        name = self._deployments[tier]
        if not name:
            raise LLMError(f"No Azure OpenAI deployment configured for tier '{tier}'")
        return name