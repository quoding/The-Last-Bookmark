"""OpenAI GPT Image 2 연동. CLAUDE.md 9.1의 파라미터를 그대로 쓴다.

`ImageGenerator` 인터페이스로 실제 호출을 분리해 테스트에서 목으로
대체할 수 있게 한다.
"""

from typing import Protocol

from app.config import get_settings


class ImageGenerator(Protocol):
    def generate(self, prompt: str) -> bytes:
        """참조 없이 새 이미지를 만든다 (초상화)."""
        ...

    def edit(self, prompt: str, reference_image_paths: list[str]) -> bytes:
        """참조 이미지를 넣어 편집한다 (장면·엔딩). 참조는 항상 초상화 1장이다."""
        ...


class OpenAIImageGenerator:
    """실제 OpenAI Images API 호출. quality=low, size=1024x1536, n=1, webp."""

    def __init__(self) -> None:
        settings = get_settings()
        self._model = settings.image_model
        self._quality = settings.image_quality
        self._size = settings.image_size
        self._api_key = settings.image_api_key

    def _client(self):
        from openai import OpenAI

        return OpenAI(api_key=self._api_key)

    def generate(self, prompt: str) -> bytes:
        import base64

        client = self._client()
        result = client.images.generate(
            model=self._model,
            prompt=prompt,
            quality=self._quality,
            size=self._size,
            n=1,
            output_format="webp",
        )
        return base64.b64decode(result.data[0].b64_json)

    def edit(self, prompt: str, reference_image_paths: list[str]) -> bytes:
        import base64

        client = self._client()
        files = [open(path, "rb") for path in reference_image_paths]
        try:
            result = client.images.edit(
                model=self._model,
                image=files,
                prompt=prompt,
                quality=self._quality,
                size=self._size,
                n=1,
                output_format="webp",
            )
        finally:
            for f in files:
                f.close()
        return base64.b64decode(result.data[0].b64_json)


class ContentPolicyRefused(Exception):
    """OpenAI 콘텐츠 정책 거부. 일반 오류와 구분해 처리한다 (CLAUDE.md 9.5)."""
