"""라이브러리 시험 — exams/exam_questions/exam_attempts (docs/specs/library-exam.md).

문항 payload 스냅샷으로 원본 항목 변경과 무관하게 채점 자립.
랭킹은 exam_attempts 실시간 집계라 별도 테이블 없음.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "e6f7a8b9c0d1"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exams",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "content_id",
            sa.BigInteger(),
            sa.ForeignKey("contents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_by",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("content_id", "round", name="uq_exams_content_round"),
        sa.CheckConstraint("status IN ('active','archived')", name="ck_exams_status"),
    )
    op.create_table(
        "exam_questions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "exam_id",
            sa.BigInteger(),
            sa.ForeignKey("exams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column(
            "item_id",
            sa.BigInteger(),
            sa.ForeignKey("learning_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("payload", JSONB(), nullable=False),
        sa.UniqueConstraint("exam_id", "seq", name="uq_exam_questions_exam_seq"),
    )
    op.create_table(
        "exam_attempts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "exam_id",
            sa.BigInteger(),
            sa.ForeignKey("exams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("correct_count", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("answers", JSONB(), nullable=True),
    )
    # 랭킹·요약 집계는 시험 단위 조회 — 커버링 인덱스로 exam 스캔 고정
    op.create_index("ix_exam_attempts_exam_user", "exam_attempts", ["exam_id", "user_id"])


def downgrade() -> None:
    op.drop_index("ix_exam_attempts_exam_user", table_name="exam_attempts")
    op.drop_table("exam_attempts")
    op.drop_table("exam_questions")
    op.drop_table("exams")
