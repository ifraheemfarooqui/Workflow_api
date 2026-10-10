def register_and_login(client, email, name="Test User", password="testpass123"):
    client.post("/users/", json={"name": name, "email": email, "password": password})
    response = client.post("/auth/login", data={"username": email, "password": password})
    return response.json()["access_token"]


def test_manager_can_create_invite(client):
    manager_token = register_and_login(client, "imanager1@test.com")
    client.headers.update({"Authorization": f"Bearer {manager_token}"})
    team_id = client.post("/teams/", json={"name": "Study Group"}).json()["id"]

    response = client.post(f"/teams/{team_id}/invites", json={"email": "invitee1@test.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert "token" in data


def test_non_manager_cannot_create_invite(client):
    manager_token = register_and_login(client, "imanager2@test.com")
    client.headers.update({"Authorization": f"Bearer {manager_token}"})
    team_id = client.post("/teams/", json={"name": "Study Group"}).json()["id"]

    member_token = register_and_login(client, "imember2@test.com")
    client.headers.update({"Authorization": f"Bearer {member_token}"})
    client.post(f"/teams/{team_id}/join")

    response = client.post(f"/teams/{team_id}/invites", json={"email": "invitee2@test.com"})
    assert response.status_code == 403


def test_non_manager_cannot_list_team_invites(client):
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


def test_registered_user_can_accept_invite(client):
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


def test_wrong_email_cannot_accept_invite(client):
    manager_token = register_and_login(client, "imanager4@test.com")
    client.headers.update({"Authorization": f"Bearer {manager_token}"})
    team_id = client.post("/teams/", json={"name": "Study Group"}).json()["id"]
    token = client.post(f"/teams/{team_id}/invites", json={"email": "invitee4@test.com"}).json()["token"]

    wrong_user_token = register_and_login(client, "wrongperson4@test.com")
    client.headers.update({"Authorization": f"Bearer {wrong_user_token}"})

    response = client.post(f"/invites/{token}/accept")
    assert response.status_code == 403


def test_unregistered_user_auto_joins_via_invite_token(client):
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