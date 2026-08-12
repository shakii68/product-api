import pytest


@pytest.fixture
def auth_headers(client, test_user):
    client.post("/register", json=test_user)
    response = client.post(
        "/login",
        data={"username": test_user["username"], "password": test_user["password"]},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.benchmark
def test_create_product_performance(client, auth_headers, benchmark):
    data = {
        "name": "Performance Test Product",
        "description": "Performance testing",
        "price": 99.99,
        "stock": 10,
    }

    def create_product():
        client.post("/products", json=data, headers=auth_headers)

    benchmark(create_product)
