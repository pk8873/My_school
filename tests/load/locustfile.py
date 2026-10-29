"""Conservative public-endpoint load scenario for a dedicated staging environment.

This scenario deliberately does not create records or submit payment forms.
It does not prove authenticated school workflows can handle a target load.
Run only against a staging system you own and are authorized to test.
"""
from locust import HttpUser, between, task


class SchoolSaathiPublicUser(HttpUser):
    # Keep the initial test gentle; ramp users in the Locust UI.
    wait_time = between(1, 3)

    @task(5)
    def health_check(self):
        with self.client.get("/health/", name="GET /health/", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Unexpected health status: {response.status_code}")
            else:
                try:
                    payload = response.json()
                except ValueError:
                    response.failure("Health endpoint did not return JSON")
                    return
                if payload.get("status") != "ok":
                    response.failure("Health endpoint status is not ok")

    @task(2)
    def login_page(self):
        # GET only: no account creation, no password attempts, no CSRF bypass.
        with self.client.get("/accounts/login/", name="GET /accounts/login/", catch_response=True) as response:
            if response.status_code not in (200, 302):
                response.failure(f"Unexpected login page status: {response.status_code}")

    @task(1)
    def service_worker(self):
        with self.client.get("/sw.js", name="GET /sw.js", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Unexpected service-worker status: {response.status_code}")
            elif "javascript" not in response.headers.get("Content-Type", "").lower():
                response.failure("Service worker response is not JavaScript")
