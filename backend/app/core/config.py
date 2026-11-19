"""Application settings. Every value is read from the environment (see /.env.example)."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    # staging = public test site: secure cookies/no API docs, but test-mode payments allowed.
    environment: Literal["development", "test", "staging", "production"] = "development"
    app_name: str = "VisaReady AI"
    public_base_url: str = "http://localhost:3000"

    database_url: str = "postgresql+psycopg://visaready:visaready_dev@localhost:5432/visaready"

    # --- security -------------------------------------------------------
    secret_key: str = Field(default="dev-insecure-change-me-dev-insecure-change-me", min_length=32)
    # 32-byte key, base64-url encoded. Used to wrap per-file data keys.
    storage_master_key: str = "ZGV2LW9ubHktbWFzdGVyLWtleS0zMi1ieXRlcy0hISE="
    access_token_minutes: int = 15
    refresh_token_days: int = 14
    password_reset_minutes: int = 30
    download_token_seconds: int = 120
    cookie_secure: bool = False
    require_staff_mfa: bool = False  # forced True in production by validate()
    login_rate_limit_per_minute: int = 10
    upload_rate_limit_per_minute: int = 30

    # --- storage --------------------------------------------------------
    storage_backend: Literal["local_encrypted", "database", "s3"] = "local_encrypted"
    storage_local_path: str = "./var/storage"

    # --- package limits (shown to the applicant before payment) --------
    assessment_price_usd: str = "33.00"
    max_documents_per_application: int = 40
    max_file_size_mb: int = 15
    included_reassessments: int = 3
    retention_days_after_completion: int = 30

    # --- AI -------------------------------------------------------------
    ai_provider: Literal["none", "anthropic", "openai"] = "none"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5-5"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1"
    ai_training_opt_in_default: bool = False

    # --- payments -------------------------------------------------------
    payment_provider: Literal["sandbox", "payhere"] = "sandbox"
    payhere_merchant_id: str | None = None
    payhere_merchant_secret: str | None = None
    payhere_app_id: str | None = None
    payhere_app_secret: str | None = None
    payhere_sandbox: bool = True
    api_public_url: str = "http://localhost:8000"

    # --- email ----------------------------------------------------------
    email_backend: Literal["outbox", "smtp"] = "outbox"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    email_from: str = "VisaReady AI <no-reply@yourdomain.com>"
    document_service_email: str = "documents@yourdomain.com"
    support_email: str = "support@yourdomain.com"

    # --- writing service ------------------------------------------------
    writing_sla_hours: int = 24
    writing_sla_warning_hours: int = 4

    @field_validator("database_url")
    @classmethod
    def _normalise_db_url(cls, v: str) -> str:
        # Hosting providers hand out postgres:// or postgresql:// URLs; we use the psycopg 3 driver.
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    def validate_for_production(self) -> list[str]:
        problems: list[str] = []
        if self.environment != "production":
            return problems
        if "dev-insecure" in self.secret_key:
            problems.append("SECRET_KEY must be set")
        if self.storage_master_key.startswith("ZGV2"):
            problems.append("STORAGE_MASTER_KEY must be set")
        if not self.cookie_secure:
            problems.append("COOKIE_SECURE must be true")
        if self.payment_provider == "sandbox":
            problems.append("PAYMENT_PROVIDER=sandbox is not allowed in production")
        return problems


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.environment in ("production", "staging"):
        if "dev-insecure" in s.secret_key or s.storage_master_key.startswith("ZGV2"):
            raise RuntimeError("SECRET_KEY and STORAGE_MASTER_KEY must be set for a public deployment")
    if s.environment == "production":
        s.require_staff_mfa = True
        problems = s.validate_for_production()
        if problems:
            raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))
    return s
