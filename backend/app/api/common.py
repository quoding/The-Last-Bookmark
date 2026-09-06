import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.engine.scene import SCENES
from app.models import Card, Image, Message
from app.models import Session as SessionModel
from app.schemas import CardState, MessageOut, SceneState


def serialize_message(m: Message) -> MessageOut:
    return MessageOut(id=str(m.id), turn=m.turn, kind=m.kind, record_type=m.record_type, text=m.text)


def get_recent_messages(db: DbSession, session_id: uuid.UUID, before_turn: int, max_turns: int = 8) -> list[Message]:
    min_turn = max(1, before_turn - max_turns)
    return list(
        db.execute(
            select(Message)
            .where(
                Message.session_id == session_id,
                Message.turn >= min_turn,
                Message.turn < before_turn,
                Message.kind.in_(("player", "reply", "narration")),
            )
            .order_by(Message.created_at)
        ).scalars().all()
    )


def get_scene_image_url(db: DbSession, session_id: uuid.UUID, scene_id: int) -> str | None:
    image = db.execute(
        select(Image).where(Image.session_id == session_id, Image.kind == "scene", Image.scene_id == scene_id)
    ).scalars().first()
    return f"/api/images/{image.id}" if image else None


def build_scene_state(db: DbSession, session_id: uuid.UUID, scene_id: int, entered: bool) -> SceneState:
    return SceneState(
        id=scene_id,
        name=SCENES[scene_id]["name"],
        entered=entered,
        image_url=get_scene_image_url(db, session_id, scene_id),
    )


def get_or_create_card(db: DbSession, session_id: uuid.UUID) -> Card:
    card = db.execute(select(Card).where(Card.session_id == session_id)).scalars().first()
    if card is None:
        card = Card(session_id=session_id)
        db.add(card)
        db.flush()
    return card


def is_card_available(session: SessionModel, card: Card) -> bool:
    return session.scene_id >= 3 and not card.decided


def serialize_card(card: Card | None) -> CardState:
    if card is None or not card.written:
        return CardState(written=False, text=None, author=None)
    return CardState(written=True, text=card.text, author=card.author)
