def register_and_login(client, email, name="Test User", password="testpass123"):
    client.post("/users/", json={"name": name, "email": email, "password": password})
    response = client.post("/auth/login", data={"username": email, "password": password})
    return response.json()["access_token"]


def setup_team_project(client, manager_email):
    manager_token = register_and_login(client, manager_email)
    client.headers.update({"Authorization": f"Bearer {manager_token}"})
    team_id = client.post("/teams/", json={"name": "Study Group"}).json()["id"]
    project_id = client.post("/projects/", json={"name": "Essay", "description": "", "team_id": team_id}).json()["id"]
    return manager_token, team_id, project_id


def test_team_member_can_create_task(client):
    manager_token, team_id, project_id = setup_team_project(client, "tmanager1@test.com")

    response = client.post("/tasks/", json={
        "title": "Write intro",
        "description": "",
        "status": "todo",
        "priority": "medium",
        "project_id": project_id,
    })
    assert response.status_code == 201
    assert response.json()["title"] == "Write intro"


def test_non_member_cannot_create_task(client):
    manager_token, team_id, project_id = setup_team_project(client, "tmanager2@test.com")

    outsider_token = register_and_login(client, "toutsider2@test.com")
    client.headers.update({"Authorization": f"Bearer {outsider_token}"})

    response = client.post("/tasks/", json={
        "title": "Write intro",
        "description": "",
        "status": "todo",
        "priority": "medium",
        "project_id": project_id,
    })
    assert response.status_code == 403


def test_cannot_assign_task_to_non_team_member(client):
    manager_token, team_id, project_id = setup_team_project(client, "tmanager3@test.com")

    outsider = client.post("/users/", json={
        "name": "Test User",
        "email": "toutsider3@test.com",
        "password": "testpass123",
    }).json()
    outsider_token = client.post("/auth/login", data={
        "username": "toutsider3@test.com",
        "password": "testpass123",
    }).json()["access_token"]

    client.headers.update({"Authorization": f"Bearer {manager_token}"})
    response = client.post("/tasks/", json={
        "title": "Write intro",
        "description": "",
        "status": "todo",
        "priority": "medium",
        "project_id": project_id,
        "assigned_to": outsider["id"],
    })
    assert response.status_code == 404


def test_member_can_update_task_status(client):
    manager_token, team_id, project_id = setup_team_project(client, "tmanager4@test.com")
    task_id = client.post("/tasks/", json={
        "title": "Write intro", "description": "", "status": "todo", "priority": "medium", "project_id": project_id,
    }).json()["id"]

    member_token = register_and_login(client, "tmember4@test.com")
    client.headers.update({"Authorization": f"Bearer {member_token}"})
    client.post(f"/teams/{team_id}/join")

    response = client.put(f"/tasks/{task_id}", json={"status": "done"})
    assert response.status_code == 200
    assert response.json()["status"] == "done"


def test_task_list_scoped_to_user_teams(client):
    manager_token, team_id, project_id = setup_team_project(client, "tmanager5@test.com")
    client.post("/tasks/", json={
        "title": "Write intro", "description": "", "status": "todo", "priority": "medium", "project_id": project_id,
    })

    outsider_token = register_and_login(client, "toutsider5@test.com")
    client.headers.update({"Authorization": f"Bearer {outsider_token}"})

    response = client.get("/tasks/")
    assert response.status_code == 200
    assert response.json() == []


def test_task_can_be_assigned_to_a_team_linked_to_its_project(client):
    manager_token, team_id, project_id = setup_team_project(client, "team-assignee-manager@test.com")
    client.headers.update({"Authorization": f"Bearer {manager_token}"})
    second_team_id = client.post("/teams/", json={"name": "Second team"}).json()["id"]
    client.post(f"/projects/{project_id}/teams", json={"team_ids": [second_team_id]})

    response = client.post("/tasks/", json={
        "title": "Shared task",
        "project_id": project_id,
        "assigned_team_id": second_team_id,
    })

    assert response.status_code == 201
    assert response.json()["assigned_team_id"] == second_team_id


def test_task_cannot_be_assigned_to_a_team_not_linked_to_its_project(client):
    manager_token, team_id, project_id = setup_team_project(client, "unlinked-team-manager@test.com")
    client.headers.update({"Authorization": f"Bearer {manager_token}"})
    second_team_id = client.post("/teams/", json={"name": "Unlinked team"}).json()["id"]

    response = client.post("/tasks/", json={
        "title": "Invalid team assignment",
        "project_id": project_id,
        "assigned_team_id": second_team_id,
    })

    assert response.status_code == 404
    assert response.json()["detail"] == "Assigned team is not linked to this project"


def test_removing_project_team_clears_task_team_assignment(client):
    manager_token, team_id, project_id = setup_team_project(client, "remove-team-manager@test.com")
    client.headers.update({"Authorization": f"Bearer {manager_token}"})
    second_team_id = client.post("/teams/", json={"name": "Assigned team"}).json()["id"]
    client.post(f"/projects/{project_id}/teams", json={"team_ids": [second_team_id]})
    task = client.post("/tasks/", json={
        "title": "Assigned task",
        "project_id": project_id,
        "assigned_team_id": second_team_id,
    }).json()

    response = client.delete(f"/projects/{project_id}/teams/{second_team_id}")
    assert response.status_code == 200
    assert client.get(f"/tasks/{task['id']}").json()["assigned_team_id"] is None