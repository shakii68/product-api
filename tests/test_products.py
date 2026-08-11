import pytest

@pytest.fixture
def auth_headers(client, test_user):
    client.post("/register", json=test_user)
    response = client.post(
        "/login",
        data={"username": test_user["username"], "password": test_user["password"]},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def product_data():
    return {
        "name": "Test Product",
        "description": "This is a test product",
        "price": 99.99,
        "stock": 10,
    }

def test_create_product(client, auth_headers):
    response = client.post("/products", json=product_data(), headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Product"
    assert data["price"] == 99.99

def test_list_products(client, auth_headers):
    client.post("/products", json=product_data(), headers=auth_headers)
    response = client.get("/products", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) >= 1

def test_get_product(client, auth_headers):
    create = client.post("/products", json=product_data(), headers=auth_headers)
    product_id = create.json()["id"]
    response = client.get(f"/products/{product_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Test Product"

def test_get_product_not_found(client, auth_headers):
    response = client.get("/products/99999", headers=auth_headers)
    assert response.status_code == 404

def test_update_product(client, auth_headers):
    create = client.post("/products", json=product_data(), headers=auth_headers)
    product_id = create.json()["id"]
    response = client.patch(
        f"/products/{product_id}",
        json={"name": "Updated Product", "price": 149.99},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Product"

def test_delete_product(client, auth_headers):
    create = client.post("/products", json=product_data(), headers=auth_headers)
    product_id = create.json()["id"]
    response = client.delete(f"/products/{product_id}", headers=auth_headers)
    assert response.status_code == 204
    response = client.get(f"/products/{product_id}", headers=auth_headers)
    assert response.status_code == 404
