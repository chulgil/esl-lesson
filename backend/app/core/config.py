"""환경 설정. 모든 시크릿은 환경변수로만 주입한다 (docs/architecture/deployment.md)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # DB
    database_url: str = "postgresql+asyncpg://englesson:englesson@localhost:5432/englesson"

    # 인증
    google_client_id: str = ""
    google_client_secret: str = ""
    jwt_secret: str = DEV_JWT_SECRET
    jwt_expires_hours: int = 24
    cookie_domain: str = ""  # 운영: .lessonaza.app / 로컬: 빈 값(호스트 쿠키)
    cookie_secure: bool = True
    admin_emails: str = ""  # 콤마 구분 — 첫 로그인 시 admin 승격

    # AI
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"
    # 번역은 빠르고 저렴한 모델로 분리
    # (sonnet-5 thinking 은 대량 배치에서 타임아웃 — 2026-07-11 실측)
    anthropic_translate_model: str = "claude-haiku-4-5-20251001"
    # 단어 인사이트 카드 생성 (항목당 1회, lazy — docs/proposal/word-insight.md)
    anthropic_insight_model: str = "claude-haiku-4-5-20251001"
    # 단어 임베딩 (유사단어/오답 선지 — P2). 미설정 시 임베딩 기능 전체 스킵
    voyage_embedding_secret: str = ""
    voyage_embedding_model: str = "voyage-3.5-lite"

    # 서비스 URL (OAuth redirect 검증용)
    public_service_url: str = "https://esl.lessonaza.app"
    public_admin_url: str = "https://esladmin.lessonaza.app"

    # 유튜브 자막 프록시 (클라우드 IP 차단 우회 — docs/specs/content-pipeline.md)
    webshare_proxy_username: str = ""
    webshare_proxy_password: str = ""
    yt_proxy_url: str = ""  # 일반 HTTP(S) 프록시 URL (webshare 미사용 시)

    # 로컬 자막 수집기 인증 토큰 (빈 값이면 에이전트 API 비활성)
    agent_token: str = ""

    # 추출 워커 (테스트에서는 비활성)
    enable_workers: bool = True

    @property
    def admin_email_set(self) -> frozenset[str]:
        return frozenset(e.strip().lower() for e in self.admin_emails.split(",") if e.strip())


def assert_production_secrets(settings: "Settings") -> None:
    """운영 신호(cookie_secure)에서 기본 JWT 시크릿이면 기동 차단 — 세션 위조 방지."""
    if settings.cookie_secure and settings.jwt_secret == DEV_JWT_SECRET:
        raise RuntimeError("JWT_SECRET is the dev default — set a real secret in .env.api")


@lru_cache
def get_settings() -> Settings:
    return Settings()
