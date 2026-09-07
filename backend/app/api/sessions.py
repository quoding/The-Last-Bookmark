import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session as DbSession

from app.api.common import (
    build_scene_state,
    get_or_create_card,
    get_scene_image_url,
    is_card_available,
    serialize_message,
)
from app.api.deps import build_image_generator, get_image_generator
from app.api.idempotency import get_cached_response, store_response
from app.auth import issue_token, require_code_id, verify_invite_code
from app.config import get_settings
from app.db import get_db
from app.engine.opening import OPENING_MESSAGES
from app.engine.scene import SCENES, get_initial_scene
from app.engine.session_admin import delete_session
from app.images.openai_images import ImageGenerator
from app.images.presets import InvalidPresetError, to_english_fragments, validate_selection
from app.images.service import generate_portrait, generate_scene_image
from app.models import Card, Image, ImageJob, Message
from app.models import Session as SessionModel
from app.schemas import (
    AuthVerifyRequest,
    AuthVerifyResponse,
    PortraitRetryRequest,
    PortraitRetryResponse,
    PortraitStatus,
    PresetSelection,
    SceneImageEntry,
    SceneState,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionDeleteResponse,
    SessionListItem,
    SessionListResponse,
    SessionStartResponse,
    SessionStateResponse,
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
            ending_title=s.ending_title if s.status in ("completed", "ended_early") else None,
            portrait_url=_image_url(s.portrait_image_id),
            created_at=s.created_at,
        )
        for s in rows
    ]
    return SessionListResponse(sessions=items)


@router.post("/sessions", response_model=SessionCreateResponse)
def create_session(
    body: SessionCreateRequest,
    background_tasks: BackgroundTasks,
    code_id: str = Depends(require_code_id),
    db: DbSession = Depends(get_db),
    generator: ImageGenerator = Depends(get_image_generator),
):
    cached = get_cached_response(db, body.request_id)
    if cached is not None:
        return SessionCreateResponse(**cached)

    selection = body.presets.model_dump()
    try:
        validate_selection(selection)
    except InvalidPresetError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    existing_session_count = db.execute(
        select(func.count()).select_from(SessionModel).where(SessionModel.code_id == code_id)
    ).scalar_one()
    if existing_session_count >= get_settings().image_budget_sessions:
        raise HTTPException(
            status_code=403,
            detail=f"이 코드로 저장할 수 있는 회차는 최대 {get_settings().image_budget_sessions}개입니다.",
        )

    # count()가 아니라 MAX(index)로 다음 번호를 정한다. 회차를 삭제할 수 있게 되면서
    # count()는 남은 개수만 셀 뿐 이제까지 쓰인 최대 번호를 보장하지 못해 충돌이 났다.
    max_index = db.execute(
        select(func.max(SessionModel.index)).where(SessionModel.code_id == code_id)
    ).scalar_one()
    next_index = (max_index or 0) + 1

    session = SessionModel(code_id=code_id, index=next_index, presets=selection)
    db.add(session)
    db.flush()
    db.add(Card(session_id=session.id))

    job = ImageJob(session_id=session.id, kind="portrait", scene_id=None, status="pending")
    db.add(job)
    db.flush()

    fragments = to_english_fragments(selection)
    portrait_image = None
    try:
        portrait_image = generate_portrait(db, generator, session.id, fragments, code_id)
        session.portrait_image_id = portrait_image.id
        job.status = "done"
        job.image_id = portrait_image.id
    except Exception as exc:  # noqa: BLE001
        job.status = "failed"
        job.error = str(exc)

    db.commit()
    db.refresh(session)

    if portrait_image is not None:
        # 초상화가 나오는 즉시 장면 4장을 미리 만들기 시작한다. 플레이어가 외형 확인
        # 화면에 머무는 동안(재생성 여부를 고민하는 시간) 그 시간을 그대로 활용해
        # 대화 화면 진입 시 대기를 줄인다.
        background_tasks.add_task(
            _run_background_scene_jobs, session.id, portrait_image.file_path, [1, 2, 3, 4]
        )

    response = SessionCreateResponse(
        id=str(session.id), index=session.index, portrait=_portrait_status(session, db)
    )
    store_response(db, body.request_id, session.id, "sessions", response.model_dump())
    db.commit()
    return response


def _reset_scene_jobs(db: DbSession, session_id: uuid.UUID) -> None:
    """초상화를 다시 그리면 이전 초상화를 참조해 만든 장면 이미지가 전부 무효가 된다.
    새로 시작할 수 있게 기존 장면 이미지·작업 행과 파일을 지운다."""
    old_paths = [
        row[0]
        for row in db.execute(
            select(Image.file_path).where(Image.session_id == session_id, Image.kind == "scene")
        ).all()
    ]
    db.execute(delete(ImageJob).where(ImageJob.session_id == session_id, ImageJob.kind == "scene"))
    db.execute(delete(Image).where(Image.session_id == session_id, Image.kind == "scene"))
    db.commit()
    for path_str in old_paths:
        path = Path(path_str)
        if path.exists():
            path.unlink(missing_ok=True)


@router.post("/sessions/{session_id}/portrait/retry", response_model=PortraitRetryResponse)
def retry_portrait(
    session_id: str,
    body: PortraitRetryRequest,
    background_tasks: BackgroundTasks,
    code_id: str = Depends(require_code_id),
    db: DbSession = Depends(get_db),
    generator: ImageGenerator = Depends(get_image_generator),
):
    session = _get_owned_session(db, code_id, session_id)

    cached = get_cached_response(db, body.request_id)
    if cached is not None:
        return PortraitRetryResponse(**cached)

    if session.portrait_confirmed:
        raise HTTPException(status_code=409, detail="이미 확정된 초상화는 다시 그릴 수 없습니다.")

    current = _portrait_status(session, db)
    is_failure_retry = current.status in ("failed", "refused")
    if not is_failure_retry and session.portrait_retry_count >= PORTRAIT_RETRY_LIMIT:
        raise HTTPException(status_code=409, detail="다시 그리기 횟수를 모두 사용했습니다.")

    # 이전 초상화를 참조해 만들었을 장면 이미지는 이제 무효다. 새로 시작한다.
    _reset_scene_jobs(db, session.id)

    job = ImageJob(session_id=session.id, kind="portrait", scene_id=None, status="pending")
    db.add(job)
    db.flush()

    fragments = to_english_fragments(session.presets)
    portrait_image = None
    try:
        portrait_image = generate_portrait(db, generator, session.id, fragments, code_id)
        session.portrait_image_id = portrait_image.id
        job.status = "done"
        job.image_id = portrait_image.id
    except Exception as exc:  # noqa: BLE001
        job.status = "failed"
        job.error = str(exc)
        session.portrait_image_id = None

    if not is_failure_retry:
        session.portrait_retry_count += 1

    db.commit()
    db.refresh(session)

    if portrait_image is not None:
        background_tasks.add_task(
            _run_background_scene_jobs, session.id, portrait_image.file_path, [1, 2, 3, 4]
        )

    response = PortraitRetryResponse(portrait=_portrait_status(session, db))
    store_response(db, body.request_id, session.id, "portrait_retry", response.model_dump())
    db.commit()
    return response


def _run_background_scene_jobs(session_id: uuid.UUID, portrait_path: str, scene_ids: list[int]):
    from app.db import get_sessionmaker

    db = get_sessionmaker()()
    session_row = db.get(SessionModel, session_id)
    if session_row is None:
        db.close()
        return  # 회차가 삭제된 뒤 실행됐다. 조용히 종료한다.
    generator = build_image_generator(session_row.code_id)
    try:
        for scene_id in scene_ids:
            # 매 반복마다 다시 확인한다. 도중에 삭제되면 나머지 장면은 만들지 않는다.
            if db.get(SessionModel, session_id) is None:
                break
            try:
                job = ImageJob(session_id=session_id, kind="scene", scene_id=scene_id, status="pending")
                db.add(job)
                db.flush()
            except Exception:  # noqa: BLE001 - 그 사이 회차가 지워졌으면 여기서 멈춘다
                db.rollback()
                break
            try:
                image = generate_scene_image(db, generator, session_id, scene_id, portrait_path, session_row.code_id)
                job.status = "done"
                job.image_id = image.id
            except Exception as exc:  # noqa: BLE001
                job.status = "failed"
                job.error = str(exc)
            try:
                db.commit()
            except Exception:  # noqa: BLE001 - 그 사이 회차가 지워졌으면 이 작업 결과는 버린다
                db.rollback()
                break
    finally:
        db.close()


@router.post("/sessions/{session_id}/start", response_model=SessionStartResponse)
def start_session(
    session_id: str,
    background_tasks: BackgroundTasks,
    code_id: str = Depends(require_code_id),
    db: DbSession = Depends(get_db),
):
    """초상화 확정. 장면 이미지는 이미 초상화가 나온 시점(회차 생성/재생성)부터
    백그라운드로 만들어지고 있으므로 여기서는 기다리지 않고 즉시 반환한다.
    아직 준비되지 않았으면 scene.image_url이 null로 온다 — 프론트가 스켈레톤을
    보여주고 폴링해야 한다(장면 2~4와 동일한 패턴)."""
    session = _get_owned_session(db, code_id, session_id)
    if session.portrait_image_id is None:
        raise HTTPException(status_code=409, detail="초상화가 없어 회차를 시작할 수 없습니다.")

    if not session.portrait_confirmed:
        session.portrait_confirmed = True

        for kind, text in OPENING_MESSAGES:
            db.add(Message(session_id=session.id, turn=0, kind=kind, text=text))

        existing = db.execute(
            select(ImageJob).where(ImageJob.session_id == session.id, ImageJob.kind == "scene")
        ).scalars().first()
        db.commit()

        if existing is None:
            # 안전망: 어떤 이유로든 초상화 확정 전에 장면 생성이 시작되지 않았다면
            # 지금 시작한다. 정상 경로에서는 회차 생성/재생성 시점에 이미 시작된다.
            portrait = db.get(Image, session.portrait_image_id)
            background_tasks.add_task(
                _run_background_scene_jobs, session.id, portrait.file_path, [1, 2, 3, 4]
            )

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


@router.get("/sessions/{session_id}", response_model=SessionStateResponse)
def get_session_state(
    session_id: str,
    code_id: str = Depends(require_code_id),
    db: DbSession = Depends(get_db),
):
    """회차 상태·메시지·이미지 복원. 재진입 시 저장된 상태를 그대로 돌려준다."""
    session = _get_owned_session(db, code_id, session_id)

    messages = db.execute(
        select(Message).where(Message.session_id == session.id).order_by(Message.turn, Message.created_at)
    ).scalars().all()

    scene_state = build_scene_state(db, session.id, session.scene_id, entered=False)
    card = get_or_create_card(db, session.id)

    scenes = [
        SceneImageEntry(
            id=scene_id,
            name=SCENES[scene_id]["name"],
            image_url=get_scene_image_url(db, session.id, scene_id),
        )
        for scene_id in sorted(SCENES)
    ]

    return SessionStateResponse(
        id=str(session.id),
        status=session.status,
        completed_turns=session.completed_turns,
        story_time=session.story_time,
        scene=scene_state,
        scenes=scenes,
        messages=[serialize_message(m) for m in messages],
        card_available=is_card_available(session, card),
        is_final_turn=session.completed_turns >= 12,
        portrait=_portrait_status(session, db),
        portrait_confirmed=session.portrait_confirmed,
        presets=PresetSelection(**session.presets),
    )


@router.delete("/sessions/{session_id}", response_model=SessionDeleteResponse)
def delete_session_endpoint(
    session_id: str,
    code_id: str = Depends(require_code_id),
    db: DbSession = Depends(get_db),
):
    """회차 삭제. 진행 중·완료 상관없이 지울 수 있다. 이미지 파일도 함께 지운다."""
    session = _get_owned_session(db, code_id, session_id)
    delete_session(db, session)
    return SessionDeleteResponse(status="deleted", id=session_id)
