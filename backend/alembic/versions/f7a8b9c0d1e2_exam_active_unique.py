"""콘텐츠당 active 시험 1개 DB 강제 (docs/specs/library-exam.md).

동시 재생성 경합으로 active 2개가 커밋되면 요약 조회(scalar_one_or_none)가
영구 500 — 부분 유니크 인덱스로 invariant 를 DB 레벨에서 보장한다
(2026-07-31 심층 리뷰 반영).
"""

from alembic import op

revision = "f7a8b9c0d1e2"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_exams_content_active",
        "exams",
        ["content_id"],
        unique=True,
        postgresql_where="status = 'active'",
    )


def downgrade() -> None:
    op.drop_index("uq_exams_content_active", table_name="exams")
