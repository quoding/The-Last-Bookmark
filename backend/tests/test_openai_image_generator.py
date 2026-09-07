"""OpenAIImageGenerator.edit()가 참조 이미지의 content-type을 명시하는지 검증한다.

실사고: open(path, "rb")만 넘기면 OpenAI SDK가 파이썬 mimetypes 모듈로
확장자를 추측하는데, 배포 환경의 mimetypes가 .webp를 모른다
(mimetypes.guess_type("x.webp") == (None, None)) -> application/octet-stream으로
업로드되어 OpenAI가 400으로 거부했다(장면 1~4 이미지 전부 실패). 이 테스트는
실제 OpenAI 클라이언트를 완전히 목으로 대체해, edit()가 항상 명시적으로
"image/webp" content-type을 붙여 보내는지 회귀 검증한다.
"""

import base64
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.images.openai_images import OpenAIImageGenerator


def test_edit_sends_explicit_webp_content_type(tmp_path, monkeypatch):
    reference = tmp_path / "portrait.webp"
    reference.write_bytes(b"fake-portrait-bytes")

    fake_response = SimpleNamespace(
        data=[SimpleNamespace(b64_json=base64.b64encode(b"fake-edited-bytes").decode())],
        usage=None,
    )
    mock_client = MagicMock()
    mock_client.images.edit.return_value = fake_response

    generator = OpenAIImageGenerator(api_key="test-key")
    monkeypatch.setattr(generator, "_client", lambda: mock_client)

    captured_bytes = {}

    def _capture_and_respond(**kwargs):
        filename, file_obj, content_type = kwargs["image"][0]
        captured_bytes["filename"] = filename
        captured_bytes["content_type"] = content_type
        captured_bytes["data"] = file_obj.read()  # 닫히기 전에 읽는다
        return fake_response

    mock_client.images.edit.side_effect = _capture_and_respond

    data, _usage = generator.edit("a prompt", [str(reference)])

    assert data == b"fake-edited-bytes"
    assert captured_bytes["filename"] == "portrait.webp"
    assert captured_bytes["content_type"] == "image/webp"
    assert captured_bytes["data"] == b"fake-portrait-bytes"
