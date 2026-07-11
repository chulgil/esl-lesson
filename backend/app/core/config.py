"""환경 설정. 모든 시크릿은 환경변수로만 주입한다 (docs/architecture/deployment.md)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # DB
    database_url: str = "postgresql+asyncpg://englesson:englesson@localhost:5432/englesson"

    # 인증
    google_client_id: str = ""
    google_client_secret: str = ""
    jwt_secret: str = "dev-only-secret-change-me"
    jwt_expires_hours: int = 24
    cookie_domain: str = ""  # 운영: .lessonaza.app / 로컬: 빈 값(호스트 쿠키)
    cookie_secure: bool = True
    admin_emails: str = ""  # 콤마 구분 — 첫 로그인 시 admin 승격

    # AI
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"

    # 서비스 URL (OAuth redirect 검증용)
    public_service_url: str = "https://esl.lessonaza.app"
    public_admin_url: str = "https://esladmin.lessonaza.app"

    # 추출 워커 (테스트에서는 비활성)
    enable_workers: bool = True

    @property
    def admin_email_set(self) -> frozenset[str]:
        return frozenset(e.strip().lower() for e in self.admin_emails.split(",") if e.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
