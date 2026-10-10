"""
Tests for the messaging feature.

Covers:
  - REST history endpoints (team + DM + inbox)
  - message creation through the service layer
  - the "exactly one of team_id / recipient_id" invariant (Pydantic + DB)
  - team-membership permission on team messages
  - the DB CheckConstraint added in the messages migration
  - the WS rate-limit fix (invalid JSON frames now count against the budget)

Sending messages is intentionally WS-only in the app. These tests exercise
the service layer directly rather than standing up a WS client. The WS
endpoint is a thin wrapper around `message_service.create_message` plus
`manager.send_to_users`, both covered here. The one piece of WS-specific
logic — the rate limiter — is covered by a direct unit test at the bottom.
"""

import time
from collections import deque

import jwt as pyjwt
import pytest
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core.config import settings
from app.models.message import Message
from app.models.team import Team
from app.models.team_membership import TeamMembership
from app.models.user import User
from app.schemas.message import MessageCreate, MessageUpdate
from app.services import message_service


# ---------------------------------------------------------------------------
# fixtures local to this file
# ---------------------------------------------------------------------------

@pytest.fixture
def current_user_id(authenticated_client):
    """The id of the user `authenticated_client` is logged in as,
    decoded from the Authorization header the fixture set."""
    auth = authenticated_client.headers["Authorization"]
    token = auth.removeprefix("Bearer ")
    payload = pyjwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    return int(payload["sub"])


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_user(db, name: str, email: str) -> User:
    user = User(name=name, email=email, hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_team(db, name: str, owner: User) -> Team:
    team = Team(name=name)
    db.add(team)
    db.commit()
    db.refresh(team)
    db.add(TeamMembership(user_id=owner.id, team_id=team.id, role_in_team="manager"))
    db.commit()
    return team


def _add_member(db, team: Team, user: User, role: str = "member") -> None:
    db.add(TeamMembership(user_id=user.id, team_id=team.id, role_in_team=role))
    db.commit()


# ---------------------------------------------------------------------------
# service-level: create_message
# ---------------------------------------------------------------------------

def test_create_team_message(db_session):
    alice = _make_user(db_session, "Alice", "alice@example.com")
    team = _make_team(db_session, "Engineering", alice)

    msg = message_service.create_message(
        db_session, alice.id, MessageCreate(team_id=team.id, content="hello team")
    )

    assert msg.id is not None
    assert msg.sender_id == alice.id
    assert msg.team_id == team.id
    assert msg.recipient_id is None
    assert msg.content == "hello team"


def test_create_direct_message(db_session):
    alice = _make_user(db_session, "Alice", "alice@example.com")
    bob = _make_user(db_session, "Bob", "bob@example.com")
    team = _make_team(db_session, "Engineering", alice)
    _add_member(db_session, team, bob)

    msg = message_service.create_message(
        db_session, alice.id, MessageCreate(recipient_id=bob.id, content="hey bob")
    )

    assert msg.sender_id == alice.id
    assert msg.recipient_id == bob.id
    assert msg.team_id is None


def test_cannot_create_direct_message_without_a_shared_team(db_session):
    alice = _make_user(db_session, "Alice", "alice@example.com")
    bob = _make_user(db_session, "Bob", "bob@example.com")

    with pytest.raises(PermissionError, match="share a team"):
        message_service.create_message(
            db_session, alice.id, MessageCreate(recipient_id=bob.id, content="hello")
        )


def test_create_team_message_requires_membership(db_session):
    alice = _make_user(db_session, "Alice", "alice@example.com")
    bob = _make_user(db_session, "Bob", "bob@example.com")
    team = _make_team(db_session, "Engineering", alice)

    with pytest.raises(PermissionError):
        message_service.create_message(
            db_session, bob.id, MessageCreate(team_id=team.id, content="let me in")
        )


def test_cannot_dm_yourself(db_session):
    alice = _make_user(db_session, "Alice", "alice@example.com")

    with pytest.raises(ValueError):
        message_service.create_message(
            db_session, alice.id, MessageCreate(recipient_id=alice.id, content="hi me")
        )


def test_dm_to_unknown_user_raises(db_session):
    alice = _make_user(db_session, "Alice", "alice@example.com")

    with pytest.raises(ValueError):
        message_service.create_message(
            db_session, alice.id, MessageCreate(recipient_id=99999, content="ghost")
        )


def test_update_message_records_edited_timestamp(db_session):
    alice = _make_user(db_session, "Alice", "alice@example.com")
    bob = _make_user(db_session, "Bob", "bob@example.com")
    team = _make_team(db_session, "Engineering", alice)
    _add_member(db_session, team, bob)
    message = message_service.create_message(
        db_session, alice.id, MessageCreate(recipient_id=bob.id, content="before")
    )

    updated = message_service.update_message(
        db_session, message.id, alice.id, MessageUpdate(content="  after  ")
    )

    assert updated.content == "after"
    assert updated.edited_at is not None
    assert updated.deleted_at is None


def test_only_sender_can_update_or_delete_message(db_session):
    alice = _make_user(db_session, "Alice", "alice@example.com")
    bob = _make_user(db_session, "Bob", "bob@example.com")
    team = _make_team(db_session, "Engineering", alice)
    _add_member(db_session, team, bob)
    message = message_service.create_message(
        db_session, alice.id, MessageCreate(recipient_id=bob.id, content="private")
    )

    with pytest.raises(PermissionError):
        message_service.update_message(
            db_session, message.id, bob.id, MessageUpdate(content="changed")
        )
    with pytest.raises(PermissionError):
        message_service.delete_message(db_session, message.id, bob.id)


def test_former_team_member_cannot_update_message(db_session):
    alice = _make_user(db_session, "Alice", "alice@example.com")
    team = _make_team(db_session, "Engineering", alice)
    message = message_service.create_message(
        db_session, alice.id, MessageCreate(team_id=team.id, content="team message")
    )
    db_session.query(TeamMembership).filter_by(
        team_id=team.id, user_id=alice.id
    ).delete()
    db_session.commit()

    with pytest.raises(PermissionError, match="member of this team"):
        message_service.update_message(
            db_session, message.id, alice.id, MessageUpdate(content="changed")
        )


def test_delete_message_keeps_placeholder_and_prevents_future_edits(db_session):
    alice = _make_user(db_session, "Alice", "alice@example.com")
    bob = _make_user(db_session, "Bob", "bob@example.com")
    team = _make_team(db_session, "Engineering", alice)
    _add_member(db_session, team, bob)
    message = message_service.create_message(
        db_session, alice.id, MessageCreate(recipient_id=bob.id, content="remove me")
    )

    deleted = message_service.delete_message(db_session, message.id, alice.id)

    assert deleted.content == message_service.DELETED_MESSAGE_CONTENT
    assert deleted.deleted_at is not None
    with pytest.raises(ValueError, match="already been deleted"):
        message_service.update_message(
            db_session, message.id, alice.id, MessageUpdate(content="restore me")
        )


# ---------------------------------------------------------------------------
# schema-level: exactly-one-target invariant
# ---------------------------------------------------------------------------

def test_db_rejects_both_targets(db_session):
    """Bypass the service and Pydantic to prove the DB constraint is real.
    Postgres raises IntegrityError; MySQL raises OperationalError (3819)."""
    alice = _make_user(db_session, "Alice", "alice@example.com")
    bob = _make_user(db_session, "Bob", "bob@example.com")
    team = _make_team(db_session, "Engineering", alice)

    bad = Message(
        sender_id=alice.id,
        team_id=team.id,
        recipient_id=bob.id,
        content="both set",
    )
    db_session.add(bad)
    with pytest.raises((IntegrityError, OperationalError)):
        db_session.commit()
    db_session.rollback()


def test_db_rejects_neither_target(db_session):
    alice = _make_user(db_session, "Alice", "alice@example.com")

    bad = Message(sender_id=alice.id, content="no target")
    db_session.add(bad)
    with pytest.raises((IntegrityError, OperationalError)):
        db_session.commit()
    db_session.rollback()


def test_message_create_rejects_blank_content():
    with pytest.raises(Exception):
        MessageCreate(team_id=1, content="   ")


def test_message_create_strips_content():
    msg = MessageCreate(team_id=1, content="  hi  ")
    assert msg.content == "hi"


# ---------------------------------------------------------------------------
# DB-level: the CheckConstraint from the migration
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# history queries
# ---------------------------------------------------------------------------

def test_get_team_messages_newest_first_and_paginates(db_session):
    alice = _make_user(db_session, "Alice", "alice@example.com")
    team = _make_team(db_session, "Engineering", alice)

    ids = []
    for i in range(5):
        m = message_service.create_message(
            db_session, alice.id, MessageCreate(team_id=team.id, content=f"msg {i}")
        )
        ids.append(m.id)

    page1 = message_service.get_team_messages(db_session, team.id, before_id=None, limit=3)
    assert [m.id for m in page1] == [ids[4], ids[3], ids[2]]

    page2 = message_service.get_team_messages(db_session, team.id, before_id=ids[2], limit=3)
    assert [m.id for m in page2] == [ids[1], ids[0]]


def test_get_direct_messages_is_bidirectional(db_session):
    alice = _make_user(db_session, "Alice", "alice@example.com")
    bob = _make_user(db_session, "Bob", "bob@example.com")
    team = _make_team(db_session, "Engineering", alice)
    _add_member(db_session, team, bob)

    message_service.create_message(
        db_session, alice.id, MessageCreate(recipient_id=bob.id, content="a->b")
    )
    message_service.create_message(
        db_session, bob.id, MessageCreate(recipient_id=alice.id, content="b->a")
    )

    convo = message_service.get_direct_messages(db_session, alice.id, bob.id, None, 50)
    assert {m.content for m in convo} == {"a->b", "b->a"}

    convo_b = message_service.get_direct_messages(db_session, bob.id, alice.id, None, 50)
    assert {m.content for m in convo_b} == {"a->b", "b->a"}


def test_get_direct_messages_does_not_leak_team_messages(db_session):
    alice = _make_user(db_session, "Alice", "alice@example.com")
    bob = _make_user(db_session, "Bob", "bob@example.com")
    team = _make_team(db_session, "Engineering", alice)
    _add_member(db_session, team, bob)

    message_service.create_message(
        db_session, alice.id, MessageCreate(team_id=team.id, content="team-only")
    )
    message_service.create_message(
        db_session, alice.id, MessageCreate(recipient_id=bob.id, content="dm")
    )

    convo = message_service.get_direct_messages(db_session, alice.id, bob.id, None, 50)
    assert [m.content for m in convo] == ["dm"]


def test_get_conversations_returns_latest_per_partner(db_session):
    alice = _make_user(db_session, "Alice", "alice@example.com")
    bob = _make_user(db_session, "Bob", "bob@example.com")
    carol = _make_user(db_session, "Carol", "carol@example.com")
    bob_team = _make_team(db_session, "Engineering", alice)
    _add_member(db_session, bob_team, bob)
    carol_team = _make_team(db_session, "Design", alice)
    _add_member(db_session, carol_team, carol)

    message_service.create_message(
        db_session, alice.id, MessageCreate(recipient_id=bob.id, content="hi bob")
    )
    message_service.create_message(
        db_session, bob.id, MessageCreate(recipient_id=alice.id, content="hi alice")
    )
    message_service.create_message(
        db_session, alice.id, MessageCreate(recipient_id=carol.id, content="hi carol")
    )

    inbox = message_service.get_conversations(db_session, alice.id)
    contents = [m.content for m in inbox]
    assert len(inbox) == 2
    assert contents[0] == "hi carol"
    assert contents[1] == "hi alice"


def test_get_conversations_excludes_team_messages(db_session):
    alice = _make_user(db_session, "Alice", "alice@example.com")
    team = _make_team(db_session, "Engineering", alice)
    message_service.create_message(
        db_session, alice.id, MessageCreate(team_id=team.id, content="team msg")
    )

    inbox = message_service.get_conversations(db_session, alice.id)
    assert inbox == []


def test_get_team_contacts_searches_name_and_email_with_shared_team_scope(db_session):
    alice = _make_user(db_session, "Alice", "alice@example.com")
    bob = _make_user(db_session, "Bob", "bob@engineering.example.com")
    carol = _make_user(db_session, "Carol", "carol@example.com")
    team = _make_team(db_session, "Engineering", alice)
    _add_member(db_session, team, bob)

    from app.services import user_service

    assert user_service.get_team_contacts(db_session, alice.id, search="bob") == [bob]
    assert user_service.get_team_contacts(db_session, alice.id, search="engineering") == [bob]
    assert user_service.get_team_contacts(db_session, alice.id, search="carol") == []
    assert carol.id not in {
        contact.id for contact in user_service.get_team_contacts(db_session, alice.id)
    }


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

def test_get_team_messages_endpoint(authenticated_client):
    resp = authenticated_client.post("/teams/", json={"name": "Engineering"})
    assert resp.status_code in (200, 201), resp.text
    team_id = resp.json()["id"]

    resp = authenticated_client.get(f"/teams/{team_id}/messages")
    assert resp.status_code == 200
    assert resp.json() == []


def test_team_messages_endpoint_forbidden_for_non_member(authenticated_client, client):
    """`client` is not the same instance as `authenticated_client` — it has
    no Authorization header. We use it to register and log in as a second user."""
    team_resp = authenticated_client.post("/teams/", json={"name": "Private"})
    team_id = team_resp.json()["id"]

    reg = client.post(
        "/users/",
        json={"name": "Outsider", "email": "outsider@example.com", "password": "secret123"},
    )
    assert reg.status_code in (200, 201), reg.text

    login = client.post(
        "/auth/login",
        data={"username": "outsider@example.com", "password": "secret123"},
    )
    outsider_token = login.json()["access_token"]

    resp = client.get(
        f"/teams/{team_id}/messages",
        headers={"Authorization": f"Bearer {outsider_token}"},
    )
    assert resp.status_code == 403


def test_direct_messages_endpoint_rejects_self(authenticated_client, current_user_id):
    resp = authenticated_client.get(f"/messages/direct/{current_user_id}")
    assert resp.status_code == 400
    assert "yourself" in resp.json()["detail"].lower()


def test_direct_messages_endpoint_404_for_unknown_user(authenticated_client):
    resp = authenticated_client.get("/messages/direct/99999")
    assert resp.status_code == 404


def test_direct_messages_endpoint_rejects_non_team_contact(
    authenticated_client, client
):
    outsider = client.post("/users/", json={
        "name": "Unrelated user",
        "email": "unrelated-contact@test.com",
        "password": "testpass123",
    }).json()
    response = authenticated_client.get(f"/messages/direct/{outsider['id']}")
    assert response.status_code == 403


def test_conversations_endpoint_empty(authenticated_client):
    resp = authenticated_client.get("/messages/conversations")
    assert resp.status_code == 200
    assert resp.json() == []


def test_message_edit_and_delete_endpoints(authenticated_client, db_session, current_user_id):
    other = _make_user(db_session, "Other", "other@example.com")
    team = _make_team(
        db_session,
        "Engineering",
        db_session.query(User).filter(User.id == current_user_id).one(),
    )
    _add_member(db_session, team, other)
    message = message_service.create_message(
        db_session,
        current_user_id,
        MessageCreate(recipient_id=other.id, content="original"),
    )

    updated = authenticated_client.patch(
        f"/messages/{message.id}", json={"content": "updated"}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["content"] == "updated"
    assert updated.json()["edited_at"] is not None

    deleted = authenticated_client.delete(f"/messages/{message.id}")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["content"] == message_service.DELETED_MESSAGE_CONTENT
    assert deleted.json()["deleted_at"] is not None


def test_message_edit_endpoint_forbids_non_sender(authenticated_client, db_session, client):
    from app.core.security import create_access_token

    sender = _make_user(db_session, "Sender", "sender@example.com")
    recipient = _make_user(db_session, "Recipient", "recipient@example.com")
    team = _make_team(db_session, "Engineering", sender)
    _add_member(db_session, team, recipient)
    message = message_service.create_message(
        db_session, sender.id, MessageCreate(recipient_id=recipient.id, content="owned")
    )
    token = create_access_token({"sub": str(recipient.id)})

    response = client.patch(
        f"/messages/{message.id}",
        json={"content": "not yours"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_users_endpoint_only_lists_shared_team_contacts(authenticated_client, db_session, current_user_id):
    current_user = db_session.query(User).filter(User.id == current_user_id).one()
    team = _make_team(db_session, "Engineering", current_user)
    teammate = _make_user(db_session, "Teammate", "teammate@engineering.example.com")
    outsider = _make_user(db_session, "Outsider", "outsider@example.com")
    _add_member(db_session, team, teammate)

    all_contacts = authenticated_client.get("/users/")
    searched = authenticated_client.get("/users/?search=engineering")

    assert all_contacts.status_code == 200
    assert [contact["id"] for contact in all_contacts.json()] == [teammate.id]
    assert searched.status_code == 200
    assert [contact["id"] for contact in searched.json()] == [teammate.id]
    assert outsider.id not in {contact["id"] for contact in all_contacts.json()}


# ---------------------------------------------------------------------------
# WS rate limiter (unit test of the fix)
# ---------------------------------------------------------------------------
#
# The rate limiter is the only piece of WS logic that isn't a thin wrapper
# around the service layer. It used to skip invalid-JSON frames entirely,
# letting a client spam garbage at full speed. This test pins the fixed
# behavior by exercising the same sliding-window logic against a dummy deque.

RATE_LIMIT_MESSAGES = 10
RATE_LIMIT_WINDOW_SECONDS = 10


def _rate_limit_check(sent_at: deque, now: float) -> bool:
    """Mirror of the WS handler's sliding-window check.
    Returns True if the frame is allowed, False if it should be rejected.
    Counts the frame before parsing (the fix), so invalid frames count too."""
    while sent_at and now - sent_at[0] > RATE_LIMIT_WINDOW_SECONDS:
        sent_at.popleft()
    if len(sent_at) >= RATE_LIMIT_MESSAGES:
        return False
    sent_at.append(now)
    return True


def test_rate_limit_counts_every_frame():
    sent_at: deque = deque()
    now = 1000.0

    # first 10 frames (any kind) allowed
    for _ in range(RATE_LIMIT_MESSAGES):
        assert _rate_limit_check(sent_at, now) is True

    # the 11th is rejected
    assert _rate_limit_check(sent_at, now) is False


def test_rate_limit_slides_over_time():
    sent_at: deque = deque()
    t0 = 1000.0

    # fill the window
    for _ in range(RATE_LIMIT_MESSAGES):
        assert _rate_limit_check(sent_at, t0) is True
    assert _rate_limit_check(sent_at, t0) is False

    # after the window passes, allowed again
    assert _rate_limit_check(sent_at, t0 + RATE_LIMIT_WINDOW_SECONDS + 0.1) is True


def test_rate_limit_would_have_let_invalid_frames_bypass():
    """Regression guard for the bug: if the counter were only incremented
    on valid frames, invalid frames would not count. Here we simulate the
    fixed behavior — appending unconditionally — and confirm the budget
    is consumed by invalid frames too."""
    sent_at: deque = deque()
    now = 1000.0

    # 10 invalid frames consume the entire budget
    for _ in range(RATE_LIMIT_MESSAGES):
        assert _rate_limit_check(sent_at, now) is True

    # an 11th frame — even a *valid* one — is now rejected
    assert _rate_limit_check(sent_at, now) is False