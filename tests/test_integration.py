def test_full_crud_flow(client):
    user = {
        "username": "integrationuser",
        "email": "integration@example.com",
        "password": "testpass123",
        "full_name": "Integration User",
    }

    register = client.post("/register", json=user)
    assert register.status_code == 201

    login = client.post(
        "/login",
        data={"username": user["username"], "password": user["password"]},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    create = client.post(
        "/products",
        json={"name": "Integration Product", "description": "Full flow",
              "price": 50, "stock": 5},
        headers=headers,
    )
    assert create.status_code == 201
    product_id = create.json()["id"]

    update = client.patch(
        f"/products/{product_id}",
        json={"name": "Updated Integration Product"},
        headers=headers,
    )
    assert update.status_code == 200

    delete = client.delete(f"/products/{product_id}", headers=headers)
    assert delete.status_code == 204
