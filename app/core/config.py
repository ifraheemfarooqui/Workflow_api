from typing import Literal
from urllib.parse import urlsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: Literal["development", "test", "staging", "production"] = "development"
    DATABASE_URL: str
    TEST_DATABASE_URL: str | None = None
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    FRONTEND_URL: str = "http://localhost:3000"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    PASSWORD_RESET_REQUEST_COOLDOWN_SECONDS: int = 60
    ACCOUNT_DELETION_CODE_EXPIRE_MINUTES: int = 10
    ACCOUNT_DELETION_CODE_COOLDOWN_SECONDS: int = 60
    ACCOUNT_DELETION_CODE_MAX_ATTEMPTS: int = 5
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str | None = None
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        hide_input_in_errors=True,
    )

    @field_validator("FRONTEND_URL")
    @classmethod
    def validate_frontend_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("FRONTEND_URL must be an HTTP(S) origin without a path")
        return value.rstrip("/")

    @field_validator("CORS_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, values: list[str]) -> list[str]:
        origins = []
        for value in values:
            parsed = urlsplit(value)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("CORS_ORIGINS entries must be HTTP(S) origins without paths")
            origins.append(value.rstrip("/"))
        if len(set(origins)) != len(origins):
            raise ValueError("CORS_ORIGINS must not contain duplicates")
        return origins

    @model_validator(mode="after")
    def validate_deployment_settings(self) -> "Settings":
        if self.TEST_DATABASE_URL is not None:
            from sqlalchemy.engine import make_url

            database_url = make_url(self.DATABASE_URL)
            test_url = make_url(self.TEST_DATABASE_URL)
            database_identity = (
                database_url.get_backend_name(),
                database_url.host.casefold() if database_url.host else None,
                database_url.port,
                database_url.database,
            )
            test_identity = (
                test_url.get_backend_name(),
                test_url.host.casefold() if test_url.host else None,
                test_url.port,
                test_url.database,
            )
            if database_identity == test_identity:
                raise ValueError("TEST_DATABASE_URL must identify a separate database from DATABASE_URL")

        if self.ENVIRONMENT in {"staging", "production"}:
            if len(self.SECRET_KEY) < 32:
                raise ValueError("SECRET_KEY must contain at least 32 characters in staging/production")
            if urlsplit(self.FRONTEND_URL).scheme != "https":
                raise ValueError("FRONTEND_URL must use HTTPS in staging/production")
            if not self.CORS_ORIGINS:
                raise ValueError("CORS_ORIGINS must contain the deployed frontend origin")
            if self.FRONTEND_URL not in self.CORS_ORIGINS:
                raise ValueError("CORS_ORIGINS must include FRONTEND_URL")
            if any(urlsplit(origin).scheme != "https" for origin in self.CORS_ORIGINS):
                raise ValueError("CORS_ORIGINS must use HTTPS in staging/production")
            if any(urlsplit(origin).hostname in {"localhost", "127.0.0.1", "::1"} for origin in self.CORS_ORIGINS):
                raise ValueError("CORS_ORIGINS cannot contain localhost in staging/production")
            if urlsplit(self.FRONTEND_URL).hostname in {"localhost", "127.0.0.1", "::1"}:
                raise ValueError("FRONTEND_URL cannot use localhost in staging/production")
            if not self.SMTP_HOST or not self.SMTP_FROM_EMAIL:
                raise ValueError("SMTP_HOST and SMTP_FROM_EMAIL are required in staging/production")
            if bool(self.SMTP_USERNAME) != bool(self.SMTP_PASSWORD):
                raise ValueError("Configure both SMTP_USERNAME and SMTP_PASSWORD, or leave both empty")
            if self.SMTP_USE_SSL == self.SMTP_USE_TLS:
                raise ValueError("Enable exactly one of SMTP_USE_SSL or SMTP_USE_TLS in staging/production")

        return self


settings = Settings()