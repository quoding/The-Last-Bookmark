from app.images.openai_images import ImageGenerator, OpenAIImageGenerator

_generator: ImageGenerator | None = None


def get_image_generator() -> ImageGenerator:
    """실제 OpenAI 클라이언트. 테스트에서는 FastAPI dependency_overrides로 교체한다."""
    global _generator
    if _generator is None:
        _generator = OpenAIImageGenerator()
    return _generator
