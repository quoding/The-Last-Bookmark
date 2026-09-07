"""프롬프트 조립 + 이미지 생성 호출 + storage 저장을 잇는 서비스 계층.

CLAUDE.md 9.4: OpenAI가 주는 URL은 만료되므로 생성 즉시 파일로 내려받아
storage/에 저장하고 DB에 경로를 기록한다.
"""

import uuid
from pathlib import Path

from sqlalchemy.orm import Session as DbSession

from app.config import get_settings
from app.images import prompts
from app.images.openai_images import ContentPolicyRefused, ImageGenerator
from app.models import Image, ImageJob
from app.usage import log_image_usage


def _storage_dir() -> Path:
    path = Path(get_settings().storage_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_image_bytes(session_id: uuid.UUID, kind: str, data: bytes) -> Path:
    storage_dir = _storage_dir()
    filename = f"{session_id}_{kind}_{uuid.uuid4().hex}.webp"
    file_path = storage_dir / filename
    file_path.write_bytes(data)
    return file_path


def generate_portrait(
    db: DbSession,
    generator: ImageGenerator,
    session_id: uuid.UUID,
    preset_fragments: dict[str, str],
    code_id: str | None = None,
) -> Image:
    prompt = prompts.portrait_prompt(preset_fragments)
    data, usage = generator.generate(prompt)
    if code_id is not None:
        log_image_usage(db, code_id, session_id, get_settings().image_model, usage)
    file_path = save_image_bytes(session_id, "portrait", data)
    image = Image(session_id=session_id, kind="portrait", scene_id=None, file_path=str(file_path))
    db.add(image)
    db.flush()
    return image


def generate_scene_image(
    db: DbSession,
    generator: ImageGenerator,
    session_id: uuid.UUID,
    scene_id: int,
    portrait_file_path: str,
    code_id: str | None = None,
) -> Image:
    prompt = prompts.scene_prompt(scene_id)
    data, usage = generator.edit(prompt, [portrait_file_path])
    if code_id is not None:
        log_image_usage(db, code_id, session_id, get_settings().image_model, usage)
    file_path = save_image_bytes(session_id, f"scene{scene_id}", data)
    image = Image(session_id=session_id, kind="scene", scene_id=scene_id, file_path=str(file_path))
    db.add(image)
    db.flush()
    return image


def generate_ending_image(
    db: DbSession,
    generator: ImageGenerator,
    session_id: uuid.UUID,
    portrait_file_path: str,
    slots: dict[str, str],
    code_id: str | None = None,
) -> Image:
    prompt = prompts.ending_prompt(**slots)
    data, usage = generator.edit(prompt, [portrait_file_path])
    if code_id is not None:
        log_image_usage(db, code_id, session_id, get_settings().image_model, usage)
    file_path = save_image_bytes(session_id, "ending", data)
    image = Image(session_id=session_id, kind="ending", scene_id=None, file_path=str(file_path))
    db.add(image)
    db.flush()
    return image


def run_image_job(
    db: DbSession,
    generator: ImageGenerator,
    job: ImageJob,
    *,
    session_id: uuid.UUID,
    code_id: str | None = None,
    portrait_file_path: str | None = None,
    preset_fragments: dict[str, str] | None = None,
    ending_slots: dict[str, str] | None = None,
) -> ImageJob:
    """image_jobs 한 행을 실행한다. 성공/실패/거부만 기록하고 두 번 생성하지 않는다."""
    if job.status == "done":
        return job
    try:
        if job.kind == "portrait":
            image = generate_portrait(db, generator, session_id, preset_fragments or {}, code_id)
        elif job.kind == "scene":
            image = generate_scene_image(
                db, generator, session_id, job.scene_id, portrait_file_path or "", code_id
            )
        elif job.kind == "ending":
            image = generate_ending_image(
                db, generator, session_id, portrait_file_path or "", ending_slots or {}, code_id
            )
        else:
            raise ValueError(f"알 수 없는 이미지 종류: {job.kind}")
    except ContentPolicyRefused as exc:
        job.status = "refused"
        job.error = str(exc)
        db.flush()
        return job
    except Exception as exc:  # noqa: BLE001 - 실패 상태로 남기고 재시도는 API에서 처리
        job.status = "failed"
        job.error = str(exc)
        db.flush()
        return job

    job.status = "done"
    job.image_id = image.id
    db.flush()
    return job
