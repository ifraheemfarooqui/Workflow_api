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