import asyncio

import pytest
from fastapi import Request
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings, settings
from app.core.exceptions import sqlalchemy_error_handler, unhandled_exception_handler
from app.db.session import engine


def build_settings(**overrides):
    values = {
        "DATABASE_URL": "mysql+pymysql://workflow:secret@db.example.test/workflow",
        "SECRET_KEY": "development-secret",
        "TEST_DATABASE_URL": None,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_settings_require_non_local_https_origins_and_mail():
    with pytest.raises(ValidationError) as error:
        build_settings(ENVIRONMENT="production")
    assert "development-secret" not in str(error.value)


def test_production_settings_accept_explicit_secure_configuration():
    settings = build_settings(
        ENVIRONMENT="staging",
        SECRET_KEY="s" * 40,
        FRONTEND_URL="https://app.example.test",
        CORS_ORIGINS=["https://app.example.test", "https://admin.example.test"],
        SMTP_HOST="smtp.example.test",
        SMTP_FROM_EMAIL="workflow@example.test",
    )

    assert settings.CORS_ORIGINS == ["https://app.example.test", "https://admin.example.test"]


@pytest.mark.parametrize(
    ("frontend_url", "origins"),
    [
        ("http://localhost:3000", ["https://app.example.test"]),
        ("https://app.example.test", ["http://localhost:3000"]),
        ("https://app.example.test", ["https://other.example.test"]),
    ],
)
def test_production_settings_reject_local_insecure_or_mismatched_origins(frontend_url, origins):
    with pytest.raises(ValidationError):
        build_settings(
            ENVIRONMENT="production",
            SECRET_KEY="s" * 40,
            FRONTEND_URL=frontend_url,
            CORS_ORIGINS=origins,
            SMTP_HOST="smtp.example.test",
            SMTP_FROM_EMAIL="workflow@example.test",
        )


def test_test_database_must_be_separate_from_application_database():
    with pytest.raises(ValidationError, match="separate database"):
        build_settings(
            TEST_DATABASE_URL="mysql+mysqldb://other:credentials@DB.example.test/workflow"
        )


def test_cors_origins_load_from_environment_as_json(monkeypatch):
    environment = {
        "ENVIRONMENT": "staging",
        "DATABASE_URL": "mysql+pymysql://workflow:secret@db.example.test/workflow",
        "SECRET_KEY": "s" * 40,
        "FRONTEND_URL": "https://app.example.test",
        "CORS_ORIGINS": '["https://app.example.test"]',
        "SMTP_HOST": "smtp.example.test",
        "SMTP_FROM_EMAIL": "workflow@example.test",
    }
    for name, value in environment.items():
        monkeypatch.setenv(name, value)

    assert Settings(_env_file=None).CORS_ORIGINS == ["https://app.example.test"]


def test_sql_statement_echo_is_disabled():
    assert engine.echo is False


def test_cors_middleware_uses_configured_origins():
    from app.main import app

    cors_middleware = next(
        middleware for middleware in app.user_middleware if middleware.cls.__name__ == "CORSMiddleware"
    )

    assert cors_middleware.kwargs["allow_origins"] == settings.CORS_ORIGINS


@pytest.mark.parametrize(
    "handler, exception",
    [
        (sqlalchemy_error_handler, SQLAlchemyError("sensitive query and parameter")),
        (unhandled_exception_handler, RuntimeError("private user information")),
    ],
)
def test_error_logs_do_not_include_exception_messages(handler, exception, caplog):
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/invites/private-token/accept",
            "headers": [],
            "query_string": b"",
            "server": ("test", 80),
            "scheme": "http",
        }
    )

    asyncio.run(handler(request, exception))

    assert "sensitive query and parameter" not in caplog.text
    assert "private user information" not in caplog.text
    assert "private-token" not in caplog.text
