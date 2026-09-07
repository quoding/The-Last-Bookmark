from fastapi import Depends

from app.auth import require_code_id
from app.config import get_settings
from app.images.openai_images import ImageGenerator, OpenAIImageGenerator

_generators: dict[str, ImageGenerator] = {}


def build_image_generator(code_id: str) -> ImageGenerator:
    """code_id별로 다른 API 키를 쓸 수 있게 클라이언트를 코드 단위로 캐시한다.

    백그라운드 작업처럼 FastAPI 의존성 주입 밖에서 code_id를 이미 알고
    있을 때 직접 호출한다.
    """
    if code_id not in _generators:
        api_key = get_settings().resolve_api_key(code_id, get_settings().image_api_key)
        _generators[code_id] = OpenAIImageGenerator(api_key=api_key)
    return _generators[code_id]


def get_image_generator(code_id: str = Depends(require_code_id)) -> ImageGenerator:
    """FastAPI 라우트용 의존성. 테스트에서는 dependency_overrides로 교체한다."""
    return build_image_generator(code_id)
