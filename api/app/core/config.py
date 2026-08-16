from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "postgresql+asyncpg://brsrlens:brsrlens@postgres:5432/brsrlens"
    redis_url: str = "redis://redis:6379/0"
    jwt_secret: str = "development-only-change-me"
    jwt_issuer: str = "brsrlens"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    verification_token_hours: int = 24
    smtp_host: str = "mailhog"
    smtp_port: int = 1025
    email_from: str = "hello@brsrlens.local"
    frontend_url: str = "http://localhost:5173"
    auth_expose_verification_token: bool = True
    public_rate_limit_per_minute: int = 120
    org_rate_limit_per_minute: int = 600
    object_store_backend: str = "local"
    object_store_local_root: str = ".data/object-store"
    filings_bucket: str = "filings-raw"
    s3_endpoint_url: str | None = None
    aws_region: str = "ap-south-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    acquisition_rate_per_second: float = Field(default=0.5, gt=0)
    acquisition_max_attempts: int = Field(default=3, ge=1, le=10)
    manual_upload_max_bytes: int = Field(default=50_000_000, ge=1)
    source_exchange_xbrl_enabled: bool = False
    source_exchange_announcements_enabled: bool = False
    source_company_ir_enabled: bool = False
    source_exchange_xbrl_url_template: str = ""
    source_exchange_announcements_url_template: str = ""
    source_nse_brsr_enabled: bool = False
    nse_brsr_portal_url: str = (
        "https://www.nseindia.com/api/corporate-bussiness-sustainabilitiy"
    )
    nse_nifty50_registry_url: str = (
        "https://nsearchives.nseindia.com/content/indices/ind_nifty50list.csv"
    )
    nse_brsr_default_fy: int = Field(default=2025, ge=2022, le=2200)
    nse_brsr_default_batch_size: int = Field(default=10, ge=1, le=50)
    nse_brsr_schedule_enabled: bool = False
    nse_brsr_refresh_hours: float = Field(default=168, ge=1, le=8760)
    nse_brsr_user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
    nse_brsr_contact: str = "legal-contact@brsrlens.local"
    llm_provider: str = "fake"
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4.1-mini"
    llm_fixture_case: str = "default"
    llm_network_enabled: bool = Field(default=False)
    embedding_model: str = "hash-embedding-v1"
    embedding_batch_size: int = Field(default=32, ge=1, le=500)
    publish_threshold: float = Field(default=0.90, ge=0, le=1)
    publish_family_accuracy_target: float = Field(default=0.98, ge=0, le=1)
    extraction_max_attempts: int = Field(default=3, ge=1, le=10)
    studio_document_max_bytes: int = Field(default=25_000_000, ge=1)
    studio_monthly_token_limit: int = Field(default=1_000_000, ge=1)
    studio_bulk_accept_confidence: float = Field(default=0.90, ge=0, le=1)
    analytics_retention_months: int = Field(default=13, ge=1, le=60)
    lead_routing_enabled: bool = False
    lead_recipient_email: str = "bd@panaceabioedge.local"
    lead_webhook_url: str | None = None
    lead_webhook_secret: str | None = None
    analytics_digest_recipients: str = "team@brsrlens.local"
    billing_ops_email: str = "ops@brsrlens.local"
    razorpay_enabled: bool = False

    @property
    def llm_config_present(self) -> bool:
        return self.llm_provider == "fake" or bool(self.llm_api_key)

    @model_validator(mode="after")
    def production_secrets_are_safe(self) -> "Settings":
        if self.app_env == "production" and (
            self.jwt_secret == "development-only-change-me" or len(self.jwt_secret) < 32
        ):
            raise ValueError("JWT_SECRET must be a unique value of at least 32 characters")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
