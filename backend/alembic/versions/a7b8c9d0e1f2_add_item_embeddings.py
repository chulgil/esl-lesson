"""item_embeddings 추가 — pgvector halfvec + HNSW (docs/proposal/word-insight.md P2).

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-13

프로드 postgres 는 pgvector 이미지(vector 0.8.2 가용 실측). CREATE EXTENSION 은
이미 존재하면 NOTICE 만 내고 통과하므로 앱 유저 권한으로도 안전 (프로드는
admin 으로 사전 생성).
"""

from alembic import op

revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 파이프라인 embed 단계 허용 (extraction_jobs.step CHECK 확장)
    op.execute("ALTER TABLE extraction_jobs DROP CONSTRAINT ck_jobs_step")
    op.execute(
        "ALTER TABLE extraction_jobs ADD CONSTRAINT ck_jobs_step "
        "CHECK (step IN ('metadata','transcript','translate','extract','embed'))"
    )
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE item_embeddings (
            item_id BIGINT PRIMARY KEY
                REFERENCES learning_items(id) ON DELETE CASCADE,
            embedding halfvec(1024) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    # 연산자 클래스는 컬럼 타입(halfvec)과 일치해야 인덱스가 사용됨
    op.execute(
        "CREATE INDEX ix_item_embeddings_hnsw ON item_embeddings "
        "USING hnsw (embedding halfvec_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE item_embeddings")
