def register_and_login(client, email, name="Test User", password="testpass123"):
    client.post("/users/", json={"name": name, "email": email, "password": password})
    response = client.post("/auth/login", data={"username": email, "password": password})
    return response.json()["access_token"]


def test_create_team_creator_becomes_manager(client):
    token = register_and_login(client, "manager@test.com")
    client.headers.update({"Authorization": f"Bearer {token}"})

    response = client.post("/teams/", json={"name": "Study Group"})
    assert response.status_code == 200
    team_id = response.json()["id"]

    members_response = client.get(f"/teams/{team_id}/members")
    members = members_response.json()
    assert len(members) == 1
    assert members[0]["role_in_team"] == "manager"


def test_user_can_join_team(client):
    token_a = register_and_login(client, "managerb@test.com")
    client.headers.update({"Authorization": f"Bearer {token_a}"})
    team_id = client.post("/teams/", json={"name": "Study Group"}).json()["id"]

    token_b = register_and_login(client, "memberb@test.com")
    client.headers.update({"Authorization": f"Bearer {token_b}"})

    response = client.post(f"/teams/{team_id}/join")
    assert response.status_code == 200
    assert response.json()["role_in_team"] == "member"

    members = client.get(f"/teams/{team_id}/members").json()
    assert len(members) == 2


def test_non_manager_cannot_update_team(client):
    token_a = register_and_login(client, "managerc@test.com")
    client.headers.update({"Authorization": f"Bearer {token_a}"})
    team_id = client.post("/teams/", json={"name": "Study Group"}).json()["id"]

    token_b = register_and_login(client, "memberc@test.com")
    client.headers.update({"Authorization": f"Bearer {token_b}"})
    client.post(f"/teams/{team_id}/join")

    response = client.put(f"/teams/{team_id}", json={"name": "Renamed"})
    assert response.status_code == 403


def test_manager_can_update_team(client):
    token = register_and_login(client, "managerd@test.com")
    client.headers.update({"Authorization": f"Bearer {token}"})
    team_id = client.post("/teams/", json={"name": "Study Group"}).json()["id"]

    response = client.put(f"/teams/{team_id}", json={"name": "Renamed Group"})
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed Group"


def test_manager_can_delete_team(client):
    token = register_and_login(client, "managere@test.com")
    client.headers.update({"Authorization": f"Bearer {token}"})
    team_id = client.post("/teams/", json={"name": "Study Group"}).json()["id"]

    response = client.delete(f"/teams/{team_id}")
    assert response.status_code == 200

    get_response = client.get(f"/teams/{team_id}")
    assert get_response.status_code == 404


def test_create_team_requires_auth(client):
    response = client.post("/teams/", json={"name": "No Auth Team"})
    assert response.status_code == 401