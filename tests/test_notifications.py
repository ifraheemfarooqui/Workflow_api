def register_and_login(client, email, name):
    client.post("/users/", json={
        "name": name,
        "email": email,
        "password": "testpass123",
    })
    response = client.post("/auth/login", data={
        "username": email,
        "password": "testpass123",
    })
    return response.json()["access_token"]


def test_task_and_comment_activity_is_notified_to_team_members(client):
    manager_token = register_and_login(client, "notification-manager@test.com", "Manager")
    client.headers.update({"Authorization": f"Bearer {manager_token}"})
    team_id = client.post("/teams/", json={"name": "Research"}).json()["id"]
    project_id = client.post("/projects/", json={
        "name": "Report",
        "description": "",
        "team_id": team_id,
    }).json()["id"]
    task_id = client.post("/tasks/", json={
        "title": "Draft",
        "project_id": project_id,
    }).json()["id"]

    member_token = register_and_login(client, "notification-member@test.com", "Member")
    client.headers.update({"Authorization": f"Bearer {member_token}"})
    assert client.post(f"/teams/{team_id}/join").status_code == 200
    assert client.put(f"/tasks/{task_id}", json={"status": "done"}).status_code == 200
    assert client.post("/comments/", json={
        "task_id": task_id,
        "content": "The draft is ready.",
    }).status_code == 201

    client.headers.update({"Authorization": f"Bearer {manager_token}"})
    notifications = client.get("/notifications/").json()
    task_update = next(item for item in notifications if item["kind"] == "task_updated")
    comment = next(item for item in notifications if item["kind"] == "comment_added")
    assert task_update["title"] == "Task updated"
    assert "status: To do → Done" in task_update["body"]
    assert "Project progress: 1/1 tasks complete." in task_update["body"]
    assert "Team progress: Research: 1/1 tasks complete." in task_update["body"]
    assert task_update["project_id"] == project_id
    assert task_update["task_id"] == task_id
    assert "The draft is ready." in comment["body"]

    read = client.patch(f"/notifications/{task_update['id']}/read")
    assert read.status_code == 200
    assert read.json()["read_at"] is not None

    client.headers.update({"Authorization": f"Bearer {member_token}"})
    assert client.patch(f"/notifications/{task_update['id']}/read").status_code == 404


def test_notification_feed_is_private(client):
    manager_token = register_and_login(client, "notification-owner@test.com", "Owner")
    client.headers.update({"Authorization": f"Bearer {manager_token}"})
    team_id = client.post("/teams/", json={"name": "Private team"}).json()["id"]
    client.post("/projects/", json={
        "name": "Private project",
        "description": "",
        "team_id": team_id,
    })

    outsider_token = register_and_login(client, "notification-outsider@test.com", "Outsider")
    client.headers.update({"Authorization": f"Bearer {outsider_token}"})
    assert client.get("/notifications/").json() == []
