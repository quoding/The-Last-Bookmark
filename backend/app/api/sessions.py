import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_image_generator
from app.auth import issue_token, require_code_id, verify_invite_code
from app.config import get_settings
from app.db import get_db
from app.engine.scene import get_initial_scene
from app.images.openai_images import ImageGenerator
from app.images.presets import InvalidPresetError, to_english_fragments, validate_selection
from app.images.service import generate_portrait, generate_scene_image
from app.models import Image, ImageJob
from app.models import Session as SessionModel
from app.schemas import (
    AuthVerifyRequest,
    AuthVerifyResponse,
    PortraitRetryResponse,
    PortraitStatus,
    SceneState,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionListItem,
    SessionListResponse,
    SessionStartResponse,
)

router = APIRouter(prefix="/api")

PORTRAIT_RETRY_LIMIT = 2


def _image_url(image_id: uuid.UUID | None) -> str | None:
    return f"/api/images/{image_id}" if image_id else None


def _portrait_status(session: SessionModel, db: DbSession) -> PortraitStatus:
    if session.portrait_image_id is not None:
        return PortraitStatus(
            status="done",
            url=_image_url(session.portrait_image_id),
            retry_count=session.portrait_retry_count,
            retry_limit=PORTRAIT_RETRY_LIMIT,
        )
    job = db.execute(
        select(ImageJob)
        .where(ImageJob.session_id == session.id, ImageJob.kind == "portrait")
        .order_by(ImageJob.created_at.desc())
    ).scalars().first()
    status = job.status if job else "pending"
    return PortraitStatus(
        status=status,
        url=None,
        retry_count=session.portrait_retry_count,
        retry_limit=PORTRAIT_RETRY_LIMIT,
    )


def _get_owned_session(db: DbSession, code_id: str, session_id: str) -> SessionModel:
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="회차를 찾을 수 없습니다.")
    session = db.get(SessionModel, sid)
    if session is None or session.code_id != code_id:
        raise HTTPException(status_code=404, detail="회차를 찾을 수 없습니다.")
    return session


@router.post("/auth/verify", response_model=AuthVerifyResponse)
def verify_code(body: AuthVerifyRequest):
    code_id = verify_invite_code(body.code)
    if code_id is None:
        raise HTTPException(status_code=401, detail="초대 코드가 올바르지 않습니다.")
    return AuthVerifyResponse(token=issue_token(code_id))


@router.get("/sessions", response_model=SessionListResponse)
def list_sessions(code_id: str = Depends(require_code_id), db: DbSession = Depends(get_db)):
    rows = db.execute(
        select(SessionModel).where(SessionModel.code_id == code_id).order_by(SessionModel.index)
    ).scalars().all()
    items = [
        SessionListItem(
            id=str(s.id),
            index=s.index,
            status=s.status,
            completed_turns=s.completed_turns,
            ending_title=s.ending_title if s.status == "completed" else None,
            portrait_url=_image_url(s.portrait_image_id),
            created_at=s.created_at,
        )
        for s in rows
    ]
    return SessionListResponse(sessions=items)


@router.post("/sessions", response_model=SessionCreateResponse)
def create_session(
    body: SessionCreateRequest,
    code_id: str = Depends(require_code_id),
    db: DbSession = Depends(get_db),
    generator: ImageGenerator = Depends(get_image_generator),
):
    selection = body.presets.model_dump()
    try:
        validate_selection(selection)
    except InvalidPresetError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    total_sessions = db.execute(select(func.count()).select_from(SessionModel)).scalar_one()
    if total_sessions >= get_settings().image_budget_sessions:
        raise HTTPException(status_code=403, detail="이미지 생성 예산을 초과해 새 회차를 시작할 수 없습니다.")

    next_index = (
        db.execute(
            select(func.count()).select_from(SessionModel).where(SessionModel.code_id == code_id)
        ).scalar_one()
        + 1
    )

    session = SessionModel(code_id=code_id, index=next_index, presets=selection)
    db.add(session)
    db.flush()

    job = ImageJob(session_id=session.id, kind="portrait", scene_id=None, status="pending")
    db.add(job)
    db.flush()

    fragments = to_english_fragments(selection)
    try:
        image = generate_portrait(db, generator, session.id, fragments)
        session.portrait_image_id = image.id
        job.status = "done"
        job.image_id = image.id
    except Exception as exc:  # noqa: BLE001
        job.status = "failed"
        job.error = str(exc)

    db.commit()
    db.refresh(session)

    return SessionCreateResponse(
        id=str(session.id), index=session.index, portrait=_portrait_status(session, db)
    )


@router.post("/sessions/{session_id}/portrait/retry", response_model=PortraitRetryResponse)
def retry_portrait(
    session_id: str,
    code_id: str = Depends(require_code_id),
    db: DbSession = Depends(get_db),
    generator: ImageGenerator = Depends(get_image_generator),
):
    session = _get_owned_session(db, code_id, session_id)
    if session.portrait_confirmed:
        raise HTTPException(status_code=409, detail="이미 확정된 초상화는 다시 그릴 수 없습니다.")

    current = _portrait_status(session, db)
    is_failure_retry = current.status in ("failed", "refused")
    if not is_failure_retry and session.portrait_retry_count >= PORTRAIT_RETRY_LIMIT:
        raise HTTPException(status_code=409, detail="다시 그리기 횟수를 모두 사용했습니다.")

    job = ImageJob(session_id=session.id, kind="portrait", scene_id=None, status="pending")
    db.add(job)
    db.flush()

    fragments = to_english_fragments(session.presets)
    try:
        image = generate_portrait(db, generator, session.id, fragments)
        session.portrait_image_id = image.id
        job.status = "done"
        job.image_id = image.id
    except Exception as exc:  # noqa: BLE001
        job.status = "failed"
        job.error = str(exc)
        session.portrait_image_id = None

    if not is_failure_retry:
        session.portrait_retry_count += 1

    db.commit()
    db.refresh(session)
    return PortraitRetryResponse(portrait=_portrait_status(session, db))


def _run_background_scene_jobs(session_id: uuid.UUID, portrait_path: str, scene_ids: list[int]):
    from app.db import get_sessionmaker

    db = get_sessionmaker()()
    generator = get_image_generator()
    try:
        for scene_id in scene_ids:
            job = ImageJob(session_id=session_id, kind="scene", scene_id=scene_id, status="pending")
            db.add(job)
            db.flush()
            try:
                image = generate_scene_image(db, generator, session_id, scene_id, portrait_path)
                job.status = "done"
                job.image_id = image.id
            except Exception as exc:  # noqa: BLE001
                job.status = "failed"
                job.error = str(exc)
            db.commit()
    finally:
        db.close()


@router.post("/sessions/{session_id}/start", response_model=SessionStartResponse)
def start_session(
    session_id: str,
    background_tasks: BackgroundTasks,
    code_id: str = Depends(require_code_id),
    db: DbSession = Depends(get_db),
    generator: ImageGenerator = Depends(get_image_generator),
):
    session = _get_owned_session(db, code_id, session_id)
    if session.portrait_image_id is None:
        raise HTTPException(status_code=409, detail="초상화가 없어 회차를 시작할 수 없습니다.")

    if not session.portrait_confirmed:
        session.portrait_confirmed = True

        portrait = db.get(Image, session.portrait_image_id)
        portrait_path = portrait.file_path

        existing = db.execute(
            select(ImageJob).where(ImageJob.session_id == session.id, ImageJob.kind == "scene")
        ).scalars().first()
        if existing is None:
            job1 = ImageJob(session_id=session.id, kind="scene", scene_id=1, status="pending")
            db.add(job1)
            db.flush()
            try:
                image = generate_scene_image(db, generator, session.id, 1, portrait_path)
                job1.status = "done"
                job1.image_id = image.id
            except Exception as exc:  # noqa: BLE001
                job1.status = "failed"
                job1.error = str(exc)

            db.commit()
            background_tasks.add_task(_run_background_scene_jobs, session.id, portrait_path, [2, 3, 4])
        else:
            db.commit()

    db.refresh(session)
    scene1_job = db.execute(
        select(ImageJob).where(
            ImageJob.session_id == session.id, ImageJob.kind == "scene", ImageJob.scene_id == 1
        )
    ).scalars().first()
    scene1_image_url = _image_url(scene1_job.image_id) if scene1_job and scene1_job.image_id else None

    initial = get_initial_scene()
    return SessionStartResponse(
        id=str(session.id),
        completed_turns=session.completed_turns,
        story_time=initial.story_time,
        scene=SceneState(id=initial.scene_id, name=initial.scene_name, entered=True, image_url=scene1_image_url),
    )
