from app.llm.client import LLMClient, OpenAILLMClient

_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = OpenAILLMClient()
    return _client
