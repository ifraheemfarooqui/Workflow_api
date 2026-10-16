import pytest
from app.models.invite import Invite
from app.services import invite_service


@pytest.fixture
def mock_invite_email(monkeypatch):
    monkeypatch.setattr(invite_service, "send_team_invite_email", lambda email, team_name, token: None)


def register_and_login(client, email, name="Test User", password="testpass123"):
    client.post("/users/", json={"name": name, "email": email, "password": password})
    response = client.post("/auth/login", data={"username": email, "password": password})
    return response.json()["access_token"]


def test_manager_can_create_invite(client, mock_invite_email):
    manager_token = register_and_login(client, "imanager1@test.com")
    client.headers.update({"Authorization": f"Bearer {manager_token}"})
    team_id = client.post("/teams/", json={"name": "Study Group"}).json()["id"]

    response = client.post(f"/teams/{team_id}/invites", json={"email": "invitee1@test.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert "token" in data


def test_invitation_email_contains_acceptance_link(monkeypatch):
    from app.core.config import settings

    captured = []
    monkeypatch.setattr(invite_service, "send_email", lambda message: captured.append(message))

    invite_service.send_team_invite_email("invitee@test.com", "Study Group", "invite-token")

    assert captured[0]["To"] == "invitee@test.com"
    assert "Study Group" in captured[0]["Subject"]
    assert f"{settings.FRONTEND_URL}/login?invite=invite-token" in captured[0].get_content()


def test_cannot_invite_existing_team_member(client):
    manager_token = register_and_login(client, "invite-existing-manager@test.com")
    client.headers.update({"Authorization": f"Bearer {manager_token}"})
    team_id = client.post("/teams/", json={"name": "Study Group"}).json()["id"]

    response = client.post(
        f"/teams/{team_id}/invites",
        json={"email": "invite-existing-manager@test.com"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "This user is already a member of the team"


def test_invitee_can_list_only_their_pending_invites(client, mock_invite_email):
    manager_token = register_and_login(client, "pending-invite-manager@test.com")
    client.headers.update({"Authorization": f"Bearer {manager_token}"})
    team_id = client.post("/teams/", json={"name": "Invited team"}).json()["id"]
    token = client.post(
        f"/teams/{team_id}/invites",
        json={"email": "pending-invitee@test.com"},
    ).json()["token"]

    invitee_token = register_and_login(client, "pending-invitee@test.com")
    client.headers.update({"Authorization": f"Bearer {invitee_token}"})

    response = client.get("/invites/mine")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["token"] == token
    assert response.json()[0]["team"]["name"] == "Invited team"

    assert client.post(f"/invites/{token}/accept").status_code == 200
    assert client.get("/invites/mine").json() == []


def test_team_invite_sends_email_even_if_recipient_has_no_account(client, monkeypatch):
    manager_token = register_and_login(client, "unregistered-invite-manager@test.com")
    client.headers.update({"Authorization": f"Bearer {manager_token}"})
    team_id = client.post("/teams/", json={"name": "Email invite team"}).json()["id"]
    sent = []
    monkeypatch.setattr(
        invite_service,
        "send_team_invite_email",
        lambda email, team_name, token: sent.append((email, team_name, token)),
    )

    response = client.post(
        f"/teams/{team_id}/invites",
        json={"email": "no-account-yet@test.com"},
    )

    assert response.status_code == 200
    assert sent == [("no-account-yet@test.com", "Email invite team", response.json()["token"])]


def test_manager_invitation_email_failure_revokes_invite(client, monkeypatch, db_session):
    manager_token = register_and_login(client, "invite-mail-manager@test.com")
    client.headers.update({"Authorization": f"Bearer {manager_token}"})
    team_id = client.post("/teams/", json={"name": "Study Group"}).json()["id"]

    def fail_delivery(email, team_name, token):
        raise OSError("SMTP error details must not be returned")

    monkeypatch.setattr(invite_service, "send_team_invite_email", fail_delivery)
    response = client.post(
        f"/teams/{team_id}/invites",
        json={"email": "invite-mail-recipient@test.com"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Team invitation email could not be sent right now."
    invite = db_session.query(Invite).filter_by(team_id=team_id).one()
    assert invite.status == "revoked"


def test_non_manager_cannot_create_invite(client):
    manager_token = register_and_login(client, "imanager2@test.com")
    client.headers.update({"Authorization": f"Bearer {manager_token}"})
    team_id = client.post("/teams/", json={"name": "Study Group"}).json()["id"]

    member_token = register_and_login(client, "imember2@test.com")
    client.headers.update({"Authorization": f"Bearer {member_token}"})
    client.post(f"/teams/{team_id}/join")

    response = client.post(f"/teams/{team_id}/invites", json={"email": "invitee2@test.com"})
    assert response.status_code == 403


def test_non_manager_cannot_list_team_invites(client, mock_invite_email):
    manager_token = register_and_login(client, "invite-list-manager@test.com")
    client.headers.update({"Authorization": f"Bearer {manager_token}"})
    team_id = client.post("/teams/", json={"name": "Private invitations"}).json()["id"]
    assert client.post(
        f"/teams/{team_id}/invites",
        json={"email": "invitee-list@test.com"},
    ).status_code == 200

    member_token = register_and_login(client, "invite-list-member@test.com")
    client.headers.update({"Authorization": f"Bearer {member_token}"})
    assert client.post(f"/teams/{team_id}/join").status_code == 200
    assert client.get(f"/teams/{team_id}/invites").status_code == 403


def test_registered_user_can_accept_invite(client, mock_invite_email):
    manager_token = register_and_login(client, "imanager3@test.com")
    client.headers.update({"Authorization": f"Bearer {manager_token}"})
    team_id = client.post("/teams/", json={"name": "Study Group"}).json()["id"]
    token = client.post(f"/teams/{team_id}/invites", json={"email": "invitee3@test.com"}).json()["token"]

    invitee_token = register_and_login(client, "invitee3@test.com")
    client.headers.update({"Authorization": f"Bearer {invitee_token}"})

    response = client.post(f"/invites/{token}/accept")
    assert response.status_code == 200

    members = client.get(f"/teams/{team_id}/members").json()
    assert len(members) == 2


def test_wrong_email_cannot_accept_invite(client, mock_invite_email):
    manager_token = register_and_login(client, "imanager4@test.com")
    client.headers.update({"Authorization": f"Bearer {manager_token}"})
    team_id = client.post("/teams/", json={"name": "Study Group"}).json()["id"]
    token = client.post(f"/teams/{team_id}/invites", json={"email": "invitee4@test.com"}).json()["token"]

    wrong_user_token = register_and_login(client, "wrongperson4@test.com")
    client.headers.update({"Authorization": f"Bearer {wrong_user_token}"})

    response = client.post(f"/invites/{token}/accept")
    assert response.status_code == 403


def test_unregistered_user_auto_joins_via_invite_token(client, mock_invite_email):
    manager_token = register_and_login(client, "imanager5@test.com")
    client.headers.update({"Authorization": f"Bearer {manager_token}"})
    team_id = client.post("/teams/", json={"name": "Study Group"}).json()["id"]
    token = client.post(f"/teams/{team_id}/invites", json={"email": "newstudent5@test.com"}).json()["token"]

    response = client.post("/users/", json={
        "name": "New Student",
        "email": "newstudent5@test.com",
        "password": "testpass123",
        "invite_token": token,
    })
    assert response.status_code == 200

    client.headers.update({"Authorization": f"Bearer {manager_token}"})
    members = client.get(f"/teams/{team_id}/members").json()
    assert len(members) == 2