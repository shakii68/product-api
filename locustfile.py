from locust import HttpUser, task, between
import uuid


class ProductUser(HttpUser):
    wait_time = between(1, 2)

    def on_start(self):
        username = f"locust_{uuid.uuid4().hex[:8]}"

        self.client.post(
            "/register",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": "testpass123",
                "full_name": "Locust User"
            }
        )

        response = self.client.post(
            "/login",
            data={
                "username": username,
                "password": "testpass123"
            }
        )

        if response.status_code == 200:
            self.headers = {
                "Authorization": f"Bearer {response.json()['access_token']}"
            }
        else:
            self.headers = {}

    @task
    def get_products(self):
        self.client.get(
            "/products",
            headers=self.headers
        )
