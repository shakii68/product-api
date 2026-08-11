def test_404_error(client):
    response = client.get("/non-existent-endpoint")
    assert response.status_code == 404
    data = response.json()
    assert data["error"] is True
    assert "message" in data

def test_validation_error(client, test_user):
    client.post("/register", json=test_user)
    login = client.post("/login", data={"username": test_user["username"], "password": test_user["password"]})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.post(
        "/products",
        json={"name": "", "description": "Bad", "price": -10, "stock": -5},
        headers=headers,
    )
    assert response.status_code in [400, 422]
    assert response.json()["error"] is True

def test_unauthorized_access(client):
    response = client.get("/users")
    assert response.status_code == 401

def test_forbidden_access(client, test_user):
    client.post("/register", json=test_user)
    login = client.post("/login", data={"username": test_user["username"], "password": test_user["password"]})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.get("/users", headers=headers)
    assert response.status_code == 403
