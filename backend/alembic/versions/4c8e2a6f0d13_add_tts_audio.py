"""TTS 오디오 캐시 — 신경망 발음 재생 (2026-08-05 음성 품질 보고).

Revision ID: 4c8e2a6f0d13
Revises: 9b7d5f3e1a2c
Create Date: 2026-08-05
"""

import sqlalchemy as sa

from alembic import op

revision = "4c8e2a6f0d13"
down_revision = "9b7d5f3e1a2c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tts_audio",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("text_key", sa.String(120), nullable=False),
        sa.Column("voice", sa.String(64), nullable=False),
        sa.Column("audio", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("text_key", "voice", name="uq_tts_text_voice"),
    )


def downgrade() -> None:
    op.drop_table("tts_audio")
