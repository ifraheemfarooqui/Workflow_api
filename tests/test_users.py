def register_and_login(client, email):
    client.post("/users/", json={
        "name": email.split("@")[0],
        "email": email,
        "password": "testpass123",
    })
    response = client.post("/auth/login", data={
        "username": email,
        "password": "testpass123",
    })
    return response.json()["access_token"]


def test_user_details_are_limited_to_self_and_team_contacts(client):
    owner_token = register_and_login(client, "profile-owner@test.com")
    client.headers.update({"Authorization": f"Bearer {owner_token}"})
    owner_id = client.get("/users/me").json()["id"]
    team_id = client.post("/teams/", json={"name": "Contact team"}).json()["id"]

    contact_token = register_and_login(client, "profile-contact@test.com")
    client.headers.update({"Authorization": f"Bearer {contact_token}"})
    assert client.post(f"/teams/{team_id}/join").status_code == 200
    assert client.get(f"/users/{owner_id}").status_code == 200

    outsider_token = register_and_login(client, "profile-outsider@test.com")
    client.headers.update({"Authorization": f"Bearer {outsider_token}"})
    assert client.get(f"/users/{owner_id}").status_code == 403
    assert client.get("/users/me").json()["id"] != owner_id


def test_user_details_require_authentication(client):
    assert client.get("/users/1").status_code == 401