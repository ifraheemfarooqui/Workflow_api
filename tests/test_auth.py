from datetime import datetime, timedelta, timezone

import pytest
from starlette.websockets import WebSocketDisconnect

from app.core import security
from app.api.routes import ws as websocket_route
from app.core.config import settings
from app.models.password_reset_token import PasswordResetToken
from app.models.account_deletion_code import AccountDeletionCode
from app.models.comment import Comment
from app.models.invite import Invite
from app.models.message import Message
from app.models.project import Project
from app.models.project_team import ProjectTeam
from app.models.task import Task
from app.models.team import Team
from app.models.team_membership import TeamMembership
from app.models.user import User
from app.core.connection_manager import manager
from app.services import password_reset_service


def test_register_user(client):
    response = client.post("/users/", json={
        "name": "Alice",
        "email": "alice@test.com",
        "password": "testpass123",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "alice@test.com"
    assert "password" not in data
    assert "hashed_password" not in data


def test_register_duplicate_email_fails(client):
    client.post("/users/", json={"name": "Alice", "email": "alice@test.com", "password": "testpass123"})
    response = client.post("/users/", json={"name": "Alice2", "email": "alice@test.com", "password": "pass456"})
    assert response.status_code == 409


def test_login_success(client):
    client.post("/users/", json={"name": "Alice", "email": "alice@test.com", "password": "testpass123"})
    response = client.post("/auth/login", data={"username": "alice@test.com", "password": "testpass123"})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_wrong_password(client):
    client.post("/users/", json={"name": "Alice", "email": "alice@test.com", "password": "testpass123"})
    response = client.post("/auth/login", data={"username": "alice@test.com", "password": "wrongpass"})
    assert response.status_code == 401


def test_user_can_update_own_profile(authenticated_client):
    response = authenticated_client.put("/users/me", json={
        "name": "Updated User",
        "email": "updated@test.com",
    })
    assert response.status_code == 200
    assert response.json()["name"] == "Updated User"
    assert response.json()["email"] == "updated@test.com"
    assert "hashed_password" not in response.json()


def test_user_cannot_change_email_to_another_users_email(authenticated_client, client):
    client.post("/users/", json={
        "name": "Other User",
        "email": "other@test.com",
        "password": "testpass123",
    })
    response = authenticated_client.put("/users/me", json={
        "name": "Test User",
        "email": "other@test.com",
    })
    assert response.status_code == 409


def test_profile_update_rejects_blank_name(authenticated_client):
    response = authenticated_client.put("/users/me", json={
        "name": "   ",
        "email": "testuser@test.com",
    })
    assert response.status_code == 422


def test_change_password_requires_current_password(authenticated_client):
    response = authenticated_client.post("/auth/change-password", json={
        "current_password": "incorrect",
        "new_password": "newpass123",
    })
    assert response.status_code == 400


def test_change_password_updates_hash_and_revokes_existing_sessions(authenticated_client, client):
    changed = authenticated_client.post("/auth/change-password", json={
        "current_password": "testpass123",
        "new_password": "newpass123",
    })
    assert changed.status_code == 200
    assert authenticated_client.get("/users/me").status_code == 401
    assert client.post("/auth/login", data={
        "username": "testuser@test.com",
        "password": "testpass123",
    }).status_code == 401
    assert client.post("/auth/login", data={
        "username": "testuser@test.com",
        "password": "newpass123",
    }).status_code == 200


def test_change_password_closes_existing_websocket_sessions(authenticated_client, db_session, monkeypatch):
    user_id = db_session.query(User.id).filter_by(email="testuser@test.com").scalar()
    monkeypatch.setattr(websocket_route, "_authenticate", lambda token: user_id)
    token = authenticated_client.headers["Authorization"].removeprefix("Bearer ")

    with authenticated_client.websocket_connect(f"/ws?token={token}") as websocket:
        assert manager._connections.get(user_id)
        response = authenticated_client.post("/auth/change-password", json={
            "current_password": "testpass123",
            "new_password": "newpass123",
        })
        assert response.status_code == 200
        with pytest.raises(WebSocketDisconnect):
            websocket.receive_json()

    assert user_id not in manager._connections


def test_websocket_closes_after_rate_limit_is_exceeded(authenticated_client, db_session, monkeypatch):
    user_id = db_session.query(User.id).filter_by(email="testuser@test.com").scalar()
    monkeypatch.setattr(websocket_route, "_authenticate", lambda token: user_id)
    monkeypatch.setattr(websocket_route, "RATE_LIMIT_MESSAGES", 2)
    token = authenticated_client.headers["Authorization"].removeprefix("Bearer ")

    with authenticated_client.websocket_connect(f"/ws?token={token}") as websocket:
        for _ in range(2):
            websocket.send_json({})
            assert websocket.receive_json()["type"] == "error"

        websocket.send_json({})
        assert websocket.receive_json()["detail"] == "You're sending messages too fast"
        with pytest.raises(WebSocketDisconnect) as disconnect:
            websocket.receive_json()

    assert disconnect.value.code == 1008
    assert user_id not in manager._connections


def test_forgot_password_is_generic_and_reset_token_is_one_time(
    authenticated_client, client, db_session, monkeypatch
):
    emailed = []
    user_id = db_session.query(User.id).filter_by(email="testuser@test.com").scalar()
    closed_user_ids = []

    async def record_closed_user(user_id):
        closed_user_ids.append(user_id)

    monkeypatch.setattr(manager, "close_user_connections", record_closed_user)
    monkeypatch.setattr(password_reset_service, "ensure_email_configured", lambda: None)
    monkeypatch.setattr(
        password_reset_service,
        "send_password_reset_email",
        lambda email, token: emailed.append((email, token)),
    )

    known = client.post("/auth/forgot-password", json={"email": "testuser@test.com"})
    unknown = client.post("/auth/forgot-password", json={"email": "missing@test.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert len(emailed) == 1
    sent_email, raw_token = emailed[0]
    assert sent_email == "testuser@test.com"

    token_record = db_session.query(PasswordResetToken).one()
    assert token_record.token_hash == security.hash_reset_token(raw_token)
    assert token_record.token_hash != raw_token

    reset = client.post("/auth/reset-password", json={
        "token": raw_token,
        "new_password": "resetpass123",
    })
    assert reset.status_code == 200
    assert authenticated_client.get("/users/me").status_code == 401
    assert client.post("/auth/reset-password", json={
        "token": raw_token,
        "new_password": "anotherpass123",
    }).status_code == 400
    assert closed_user_ids == [user_id]
    assert client.post("/auth/login", data={
        "username": "testuser@test.com",
        "password": "resetpass123",
    }).status_code == 200


def test_forgot_password_cooldown_does_not_send_another_email(
    client, monkeypatch
):
    emailed = []
    monkeypatch.setattr(settings, "PASSWORD_RESET_REQUEST_COOLDOWN_SECONDS", 600)
    monkeypatch.setattr(password_reset_service, "ensure_email_configured", lambda: None)
    monkeypatch.setattr(
        password_reset_service,
        "send_password_reset_email",
        lambda email, token: emailed.append((email, token)),
    )
    client.post("/users/", json={
        "name": "Test User",
        "email": "testuser@test.com",
        "password": "testpass123",
    })
    first = client.post("/auth/forgot-password", json={"email": "testuser@test.com"})
    second = client.post("/auth/forgot-password", json={"email": "testuser@test.com"})
    assert first.status_code == second.status_code == 202
    assert first.json() == second.json()
    assert len(emailed) == 1


def test_password_reset_email_failure_does_not_log_email_or_token(client, db_session, monkeypatch, caplog):
    monkeypatch.setattr(password_reset_service, "ensure_email_configured", lambda: None)

    def fail_sending_email(email, token):
        raise OSError(f"SMTP rejected {email}; reset token {token}")

    monkeypatch.setattr(password_reset_service, "send_password_reset_email", fail_sending_email)
    client.post("/users/", json={
        "name": "Test User",
        "email": "testuser@test.com",
        "password": "testpass123",
    })

    response = client.post("/auth/forgot-password", json={"email": "testuser@test.com"})

    assert response.status_code == 503
    assert "testuser@test.com" not in caplog.text
    assert "SMTP rejected" not in caplog.text
    assert "SMTP rejected" not in response.text
    assert db_session.query(PasswordResetToken).count() == 0


def test_reset_password_rejects_expired_token(client, db_session):
    response = client.post("/users/", json={
        "name": "Test User",
        "email": "testuser@test.com",
        "password": "testpass123",
    })
    user_id = response.json()["id"]
    raw_token = security.generate_password_reset_token()
    db_session.add(PasswordResetToken(
        user_id=user_id,
        token_hash=security.hash_reset_token(raw_token),
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    ))
    db_session.commit()

    reset = client.post("/auth/reset-password", json={
        "token": raw_token,
        "new_password": "resetpass123",
    })
    assert reset.status_code == 400
    saved_user = db_session.query(User).filter_by(id=user_id).one()
    assert not security.verify_password("resetpass123", saved_user.hashed_password)


def test_account_deletion_preserves_shared_history_and_revokes_account(
    authenticated_client, client, db_session, monkeypatch
):
    user = db_session.query(User).filter_by(email="testuser@test.com").one()
    team = Team(name="Shared team")
    project = Project(name="Shared project")
    db_session.add_all([team, project])
    db_session.flush()
    db_session.add_all([
        TeamMembership(user_id=user.id, team_id=team.id, role_in_team="member"),
        ProjectTeam(team_id=team.id, project_id=project.id),
    ])
    task = Task(title="Keep this task", project_id=project.id, assigned_to=user.id)
    db_session.add(task)
    db_session.flush()
    comment = Comment(content="Keep this comment", task_id=task.id, user_id=user.id)
    message = Message(
        sender_id=user.id,
        team_id=team.id,
        recipient_id=None,
        content="Keep this message",
    )
    other_user = User(
        name="Other User",
        email="other@test.com",
        hashed_password=security.hash_password("testpass123"),
    )
    db_session.add(other_user)
    db_session.flush()
    invites = [
        Invite(
            team_id=team.id,
            invited_by=user.id,
            email="invitee@test.com",
            token="created-by-deleted-user",
        ),
        Invite(
            team_id=team.id,
            invited_by=other_user.id,
            email="TESTUSER@test.com",
            token="addressed-to-deleted-user",
        ),
    ]
    db_session.add_all([comment, message, *invites])
    db_session.commit()

    mailed = []
    closed_user_ids = []

    async def record_closed_user(user_id):
        closed_user_ids.append(user_id)

    monkeypatch.setattr(manager, "close_user_connections", record_closed_user)
    monkeypatch.setattr(password_reset_service, "ensure_email_configured", lambda: None)
    monkeypatch.setattr(
        password_reset_service,
        "send_account_deletion_code",
        lambda email, code: mailed.append((email, code)),
    )
    request = authenticated_client.post("/users/me/deletion/request", json={
        "current_password": "testpass123",
    })
    assert request.status_code == 202
    assert mailed[0][0] == user.email
    code_record = db_session.query(AccountDeletionCode).one()
    assert code_record.code_hash != mailed[0][1]

    deleted = authenticated_client.post("/users/me/deletion/confirm", json={
        "code": mailed[0][1],
    })
    assert deleted.status_code == 200
    assert closed_user_ids == [user.id]
    assert authenticated_client.get("/users/me").status_code == 401

    db_session.expire_all()
    deleted_user = db_session.query(User).filter_by(id=user.id).one()
    assert deleted_user.is_deleted is True
    assert deleted_user.name == "Deleted user"
    assert deleted_user.email.endswith("@deleted.invalid")
    assert db_session.query(TeamMembership).filter_by(user_id=user.id).count() == 0
    assert db_session.query(Task).filter_by(id=task.id).one().assigned_to is None
    assert db_session.query(Comment).filter_by(id=comment.id).one().user_id is None
    assert db_session.query(Message).filter_by(id=message.id).one().sender_id is None
    assert deleted_user.name == "Deleted user"
    assert deleted_user.email == f"deleted-{user.id}@deleted.invalid"
    assert db_session.query(Invite).filter(
        (Invite.invited_by == user.id) | (Invite.email.ilike("testuser@test.com"))
    ).count() == 0
    assert db_session.query(Invite).filter_by(token="created-by-deleted-user").count() == 0
    assert db_session.query(Invite).filter_by(token="addressed-to-deleted-user").count() == 0
    assert db_session.query(Comment).filter_by(id=comment.id).one().content == "Keep this comment"
    assert db_session.query(Message).filter_by(id=message.id).one().content == "Keep this message"
    assert client.post("/auth/login", data={
        "username": "testuser@test.com",
        "password": "testpass123",
    }).status_code == 401


def test_account_deletion_requires_correct_password_and_blocks_only_team_manager(
    authenticated_client, db_session
):
    created_team = authenticated_client.post("/teams/", json={"name": "Only-managed"})
    assert created_team.status_code == 200
    wrong_password = authenticated_client.post("/users/me/deletion/request", json={
        "current_password": "wrong-password",
    })
    assert wrong_password.status_code == 400

    blocked = authenticated_client.post("/users/me/deletion/request", json={
        "current_password": "testpass123",
    })
    assert blocked.status_code == 409
    assert "Transfer manager access" in blocked.json()["detail"]

    assert db_session.query(AccountDeletionCode).count() == 0
    assert authenticated_client.post("/users/me/deletion/confirm", json={
        "code": "000000",
    }).status_code == 400


def test_account_deletion_email_failure_revokes_code(
    authenticated_client, db_session, monkeypatch, caplog
):
    monkeypatch.setattr(password_reset_service, "ensure_email_configured", lambda: None)

    def fail_sending_email(email, code):
        raise OSError(f"SMTP rejected {email}; deletion code {code}")

    monkeypatch.setattr(
        password_reset_service,
        "send_account_deletion_code",
        fail_sending_email,
    )
    response = authenticated_client.post("/users/me/deletion/request", json={
        "current_password": "testpass123",
    })

    assert response.status_code == 503
    assert "testuser@test.com" not in caplog.text
    assert "SMTP rejected" not in caplog.text
    assert "SMTP rejected" not in response.text
    assert db_session.query(AccountDeletionCode).count() == 0


def test_account_deletion_codes_expire_and_stop_after_max_attempts(
    authenticated_client, db_session, monkeypatch
):
    emailed = []
    monkeypatch.setattr(settings, "ACCOUNT_DELETION_CODE_MAX_ATTEMPTS", 2)
    monkeypatch.setattr(settings, "ACCOUNT_DELETION_CODE_COOLDOWN_SECONDS", 0)
    monkeypatch.setattr(password_reset_service, "ensure_email_configured", lambda: None)
    monkeypatch.setattr(
        password_reset_service,
        "send_account_deletion_code",
        lambda email, code: emailed.append((email, code)),
    )
    request = authenticated_client.post("/users/me/deletion/request", json={
        "current_password": "testpass123",
    })
    assert request.status_code == 202
    valid_code = emailed[-1][1]
    wrong_code = "000000" if valid_code != "000000" else "000001"

    for _ in range(settings.ACCOUNT_DELETION_CODE_MAX_ATTEMPTS):
        rejected = authenticated_client.post("/users/me/deletion/confirm", json={
            "code": wrong_code,
        })
        assert rejected.status_code == 400

    assert db_session.query(AccountDeletionCode).one().attempts == 2
    assert authenticated_client.post("/users/me/deletion/confirm", json={
        "code": valid_code,
    }).status_code == 400
    assert db_session.query(User).filter_by(email="testuser@test.com").one().is_deleted is False

    second_request = authenticated_client.post("/users/me/deletion/request", json={
        "current_password": "testpass123",
    })
    assert second_request.status_code == 202
    expired_record = (
        db_session.query(AccountDeletionCode)
        .filter_by(user_id=db_session.query(User.id).filter_by(email="testuser@test.com").scalar())
        .order_by(AccountDeletionCode.created_at.desc())
        .first()
    )
    expired_record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    expired = authenticated_client.post("/users/me/deletion/confirm", json={
        "code": emailed[-1][1],
    })
    assert expired.status_code == 400
    assert db_session.query(User).filter_by(email="testuser@test.com").one().is_deleted is False