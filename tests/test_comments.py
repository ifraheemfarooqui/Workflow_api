def register_and_login(client, email, name="Test User", password="testpass123"):
    client.post("/users/", json={"name": name, "email": email, "password": password})
    response = client.post("/auth/login", data={"username": email, "password": password})
    return response.json()["access_token"]


def setup_team_project_task(client, manager_email):
    manager_token = register_and_login(client, manager_email)
    client.headers.update({"Authorization": f"Bearer {manager_token}"})
    team_id = client.post("/teams/", json={"name": "Study Group"}).json()["id"]
    project_id = client.post("/projects/", json={"name": "Essay", "description": "", "team_id": team_id}).json()["id"]
    task_id = client.post("/tasks/", json={
        "title": "Write intro", "description": "", "status": "todo", "priority": "medium", "project_id": project_id,
    }).json()["id"]
    return manager_token, team_id, project_id, task_id


def test_member_can_comment(client):
    manager_token, team_id, project_id, task_id = setup_team_project_task(client, "cmanager1@test.com")

    response = client.post("/comments/", json={"content": "Looks good", "task_id": task_id})
    assert response.status_code == 201
    assert response.json()["content"] == "Looks good"


def test_non_member_cannot_comment(client):
    manager_token, team_id, project_id, task_id = setup_team_project_task(client, "cmanager2@test.com")

    outsider_token = register_and_login(client, "coutsider2@test.com")
    client.headers.update({"Authorization": f"Bearer {outsider_token}"})

    response = client.post("/comments/", json={"content": "Looks good", "task_id": task_id})
    assert response.status_code == 403


def test_user_cannot_edit_others_comment(client):
    manager_token, team_id, project_id, task_id = setup_team_project_task(client, "cmanager3@test.com")
    comment_id = client.post("/comments/", json={"content": "Original", "task_id": task_id}).json()["id"]

    member_token = register_and_login(client, "cmember3@test.com")
    client.headers.update({"Authorization": f"Bearer {member_token}"})
    client.post(f"/teams/{team_id}/join")

    response = client.put(f"/comments/{comment_id}", json={"content": "Edited by someone else"})
    assert response.status_code == 403


def test_owner_can_edit_own_comment(client):
    manager_token, team_id, project_id, task_id = setup_team_project_task(client, "cmanager4@test.com")
    comment_id = client.post("/comments/", json={"content": "Original", "task_id": task_id}).json()["id"]

    response = client.put(f"/comments/{comment_id}", json={"content": "Edited"})
    assert response.status_code == 200
    assert response.json()["content"] == "Edited"


def test_project_manager_can_edit_others_comment(client):
    manager_token, team_id, project_id, task_id = setup_team_project_task(client, "cmanager5@test.com")

    member_token = register_and_login(client, "cmember5@test.com")
    client.headers.update({"Authorization": f"Bearer {member_token}"})
    client.post(f"/teams/{team_id}/join")
    comment_id = client.post("/comments/", json={"content": "Original", "task_id": task_id}).json()["id"]

    client.headers.update({"Authorization": f"Bearer {manager_token}"})
    response = client.put(f"/comments/{comment_id}", json={"content": "Edited by manager"})
    assert response.status_code == 200


def test_non_member_cannot_read_comments_or_change_own_comment_after_removal(client):
    manager_token, team_id, project_id, task_id = setup_team_project_task(
        client, "comment-access-manager@test.com"
    )
    member_token = register_and_login(client, "comment-access-member@test.com")
    client.headers.update({"Authorization": f"Bearer {member_token}"})
    assert client.post(f"/teams/{team_id}/join").status_code == 200
    member_id = client.get("/users/me").json()["id"]
    comment_id = client.post(
        "/comments/", json={"content": "Private comment", "task_id": task_id}
    ).json()["id"]

    client.headers.update({"Authorization": f"Bearer {manager_token}"})
    assert client.delete(f"/teams/{team_id}/members/{member_id}").status_code == 200

    client.headers.update({"Authorization": f"Bearer {member_token}"})
    assert client.get(f"/comments/{comment_id}").status_code == 403
    assert client.get(f"/comments/?task_id={task_id}").json() == []
    assert client.put(
        f"/comments/{comment_id}", json={"content": "Changed after removal"}
    ).status_code == 403
    assert client.delete(f"/comments/{comment_id}").status_code == 403