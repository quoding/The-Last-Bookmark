from fastapi import Depends

from app.auth import require_code_id
from app.config import get_settings
from app.llm.client import LLMClient, OpenAILLMClient

_clients: dict[str, LLMClient] = {}


def build_llm_client(code_id: str) -> LLMClient:
    """code_id별로 다른 API 키를 쓸 수 있게 클라이언트를 코드 단위로 캐시한다."""
    if code_id not in _clients:
        api_key = get_settings().resolve_api_key(code_id, get_settings().llm_api_key)
        _clients[code_id] = OpenAILLMClient(api_key=api_key)
    return _clients[code_id]


def get_llm_client(code_id: str = Depends(require_code_id)) -> LLMClient:
    return build_llm_client(code_id)
