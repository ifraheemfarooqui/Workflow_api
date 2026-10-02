def register_and_login(client, email, name="Test User", password="testpass123"):
    client.post("/users/", json={"name": name, "email": email, "password": password})
    response = client.post("/auth/login", data={"username": email, "password": password})
    return response.json()["access_token"]


def create_team(client, token, name="Study Group"):
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client.post("/teams/", json={"name": name}).json()["id"]


def test_team_member_can_create_project(client):
    manager_token = register_and_login(client, "pmanager1@test.com")
    team_id = create_team(client, manager_token)

    member_token = register_and_login(client, "pmember1@test.com")
    client.headers.update({"Authorization": f"Bearer {member_token}"})
    client.post(f"/teams/{team_id}/join")

    response = client.post("/projects/", json={"name": "Essay", "description": "Final paper", "team_id": team_id})
    assert response.status_code == 200
    assert response.json()["name"] == "Essay"


def test_non_member_cannot_create_project(client):
    manager_token = register_and_login(client, "pmanager2@test.com")
    team_id = create_team(client, manager_token)

    outsider_token = register_and_login(client, "poutsider2@test.com")
    client.headers.update({"Authorization": f"Bearer {outsider_token}"})

    response = client.post("/projects/", json={"name": "Essay", "description": "Final paper", "team_id": team_id})
    assert response.status_code == 403


def test_non_manager_cannot_update_project(client):
    manager_token = register_and_login(client, "pmanager3@test.com")
    team_id = create_team(client, manager_token)
    project_id = client.post("/projects/", json={"name": "Essay", "description": "", "team_id": team_id}).json()["id"]

    member_token = register_and_login(client, "pmember3@test.com")
    client.headers.update({"Authorization": f"Bearer {member_token}"})
    client.post(f"/teams/{team_id}/join")

    response = client.put(f"/projects/{project_id}", json={"name": "Renamed"})
    assert response.status_code == 403


def test_manager_can_update_project(client):
    manager_token = register_and_login(client, "pmanager4@test.com")
    team_id = create_team(client, manager_token)
    project_id = client.post("/projects/", json={"name": "Essay", "description": "", "team_id": team_id}).json()["id"]

    response = client.put(f"/projects/{project_id}", json={"name": "Renamed"})
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed"


def test_manager_can_delete_project(client):
    manager_token = register_and_login(client, "pmanager5@test.com")
    team_id = create_team(client, manager_token)
    project_id = client.post("/projects/", json={"name": "Essay", "description": "", "team_id": team_id}).json()["id"]

    response = client.delete(f"/projects/{project_id}")
    assert response.status_code == 200

    get_response = client.get(f"/projects/{project_id}")
    assert get_response.status_code == 404


def test_manager_can_add_second_team_to_project(client):
    manager_token = register_and_login(client, "pmanager6@test.com")
    team_id = create_team(client, manager_token, "Team A")
    project_id = client.post("/projects/", json={"name": "Essay", "description": "", "team_id": team_id}).json()["id"]

    second_team_id = client.post("/teams/", json={"name": "Team B"}).json()["id"]

    response = client.post(f"/projects/{project_id}/teams", json={"team_ids": [second_team_id]})
    assert response.status_code == 200
    assert len(response.json()) == 1

    teams_response = client.get(f"/projects/{project_id}/teams")
    assert len(teams_response.json()) == 2