"""회차 삭제 캐스케이드를 위해 FK에 ON DELETE 지정

Revision ID: 194bd16e37e3
Revises: 8a94c3a48e67
Create Date: 2026-09-08 00:30:28.017333

DELETE /api/sessions/{id}를 Python에서 자식 테이블을 순서대로 지우는
방식으로 구현했더니, 장면 이미지를 만드는 BackgroundTasks가 삭제 도중
새 이미지 행을 커밋해 FK 위반(500)이 나는 경합이 실제로 발생했다.
이미지 1장 생성에 20~30초가 걸려 재시도로 따라잡을 수 없었다. 대신
session_id를 참조하는 모든 FK에 ON DELETE CASCADE(또는 SET NULL)를
걸어, `DELETE FROM sessions` 한 문장으로 DB가 원자적으로 처리하게
한다. api_usage_logs만 비용 집계 기록이라 CASCADE 대신 SET NULL로
남긴다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '194bd16e37e3'
down_revision: Union[str, None] = '8a94c3a48e67'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('api_usage_logs_session_id_fkey', 'api_usage_logs', type_='foreignkey')
    op.create_foreign_key(
        'api_usage_logs_session_id_fkey', 'api_usage_logs', 'sessions', ['session_id'], ['id'], ondelete='SET NULL'
    )

    op.drop_constraint('card_session_id_fkey', 'card', type_='foreignkey')
    op.create_foreign_key('card_session_id_fkey', 'card', 'sessions', ['session_id'], ['id'], ondelete='CASCADE')

    op.drop_constraint('confirmed_events_session_id_fkey', 'confirmed_events', type_='foreignkey')
    op.drop_constraint('confirmed_events_source_message_id_fkey', 'confirmed_events', type_='foreignkey')
    op.create_foreign_key(
        'confirmed_events_source_message_id_fkey',
        'confirmed_events', 'messages', ['source_message_id'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'confirmed_events_session_id_fkey',
        'confirmed_events', 'sessions', ['session_id'], ['id'], ondelete='CASCADE',
    )

    op.drop_constraint('image_jobs_session_id_fkey', 'image_jobs', type_='foreignkey')
    op.drop_constraint('image_jobs_image_id_fkey', 'image_jobs', type_='foreignkey')
    op.create_foreign_key(
        'image_jobs_image_id_fkey', 'image_jobs', 'images', ['image_id'], ['id'], ondelete='SET NULL'
    )
    op.create_foreign_key(
        'image_jobs_session_id_fkey', 'image_jobs', 'sessions', ['session_id'], ['id'], ondelete='CASCADE'
    )

    op.drop_constraint('images_session_id_fkey', 'images', type_='foreignkey')
    op.create_foreign_key(
        'images_session_id_fkey', 'images', 'sessions', ['session_id'], ['id'], ondelete='CASCADE'
    )

    op.drop_constraint('messages_session_id_fkey', 'messages', type_='foreignkey')
    op.create_foreign_key(
        'messages_session_id_fkey', 'messages', 'sessions', ['session_id'], ['id'], ondelete='CASCADE'
    )

    op.drop_constraint('requests_session_id_fkey', 'requests', type_='foreignkey')
    op.create_foreign_key(
        'requests_session_id_fkey', 'requests', 'sessions', ['session_id'], ['id'], ondelete='CASCADE'
    )

    op.drop_constraint('scene_events_session_id_fkey', 'scene_events', type_='foreignkey')
    op.create_foreign_key(
        'scene_events_session_id_fkey', 'scene_events', 'sessions', ['session_id'], ['id'], ondelete='CASCADE'
    )

    op.drop_constraint('fk_sessions_portrait_image_id', 'sessions', type_='foreignkey')
    op.drop_constraint('fk_sessions_ending_image_id', 'sessions', type_='foreignkey')
    op.create_foreign_key(
        'fk_sessions_ending_image_id', 'sessions', 'images', ['ending_image_id'], ['id'],
        ondelete='SET NULL', use_alter=True,
    )
    op.create_foreign_key(
        'fk_sessions_portrait_image_id', 'sessions', 'images', ['portrait_image_id'], ['id'],
        ondelete='SET NULL', use_alter=True,
    )


def downgrade() -> None:
    op.drop_constraint('fk_sessions_portrait_image_id', 'sessions', type_='foreignkey')
    op.drop_constraint('fk_sessions_ending_image_id', 'sessions', type_='foreignkey')
    op.create_foreign_key(
        'fk_sessions_ending_image_id', 'sessions', 'images', ['ending_image_id'], ['id'], use_alter=True
    )
    op.create_foreign_key(
        'fk_sessions_portrait_image_id', 'sessions', 'images', ['portrait_image_id'], ['id'], use_alter=True
    )

    op.drop_constraint('scene_events_session_id_fkey', 'scene_events', type_='foreignkey')
    op.create_foreign_key('scene_events_session_id_fkey', 'scene_events', 'sessions', ['session_id'], ['id'])

    op.drop_constraint('requests_session_id_fkey', 'requests', type_='foreignkey')
    op.create_foreign_key('requests_session_id_fkey', 'requests', 'sessions', ['session_id'], ['id'])

    op.drop_constraint('messages_session_id_fkey', 'messages', type_='foreignkey')
    op.create_foreign_key('messages_session_id_fkey', 'messages', 'sessions', ['session_id'], ['id'])

    op.drop_constraint('images_session_id_fkey', 'images', type_='foreignkey')
    op.create_foreign_key('images_session_id_fkey', 'images', 'sessions', ['session_id'], ['id'])

    op.drop_constraint('image_jobs_session_id_fkey', 'image_jobs', type_='foreignkey')
    op.drop_constraint('image_jobs_image_id_fkey', 'image_jobs', type_='foreignkey')
    op.create_foreign_key('image_jobs_image_id_fkey', 'image_jobs', 'images', ['image_id'], ['id'])
    op.create_foreign_key('image_jobs_session_id_fkey', 'image_jobs', 'sessions', ['session_id'], ['id'])

    op.drop_constraint('confirmed_events_source_message_id_fkey', 'confirmed_events', type_='foreignkey')
    op.drop_constraint('confirmed_events_session_id_fkey', 'confirmed_events', type_='foreignkey')
    op.create_foreign_key(
        'confirmed_events_source_message_id_fkey', 'confirmed_events', 'messages', ['source_message_id'], ['id']
    )
    op.create_foreign_key(
        'confirmed_events_session_id_fkey', 'confirmed_events', 'sessions', ['session_id'], ['id']
    )

    op.drop_constraint('card_session_id_fkey', 'card', type_='foreignkey')
    op.create_foreign_key('card_session_id_fkey', 'card', 'sessions', ['session_id'], ['id'])

    op.drop_constraint('api_usage_logs_session_id_fkey', 'api_usage_logs', type_='foreignkey')
    op.create_foreign_key('api_usage_logs_session_id_fkey', 'api_usage_logs', 'sessions', ['session_id'], ['id'])
