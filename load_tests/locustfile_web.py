import random
from uuid import uuid4

from locust import HttpUser, between, events, task
from locust.runners import MasterRunner


class VideoUploadUser(HttpUser):
    wait_time = between(0.1, 0.5)
    created_video_ids: list[str] = []

    def on_start(self):
        password = "TestPassword123!"
        email = f"loadtest_{uuid4().hex}@example.com"
        with self.client.post(
            "/api/auth/signup",
            json={
                "email": email,
                "password1": password,
                "password2": password,
                "first_name": "Load",
                "last_name": "Test",
                "city": "TestCity",
                "country": "CO",
            },
            name="/api/auth/signup",
            catch_response=True,
        ) as response:
            if response.status_code not in [200, 201, 400]:
                response.failure(f"Signup failed with status {response.status_code}")
        with self.client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
            name="/api/auth/login",
            catch_response=True,
        ) as login_response:
            if login_response.status_code == 200:
                data = login_response.json()
                self.token = data.get("access_token")
                self.headers = {"Authorization": f"Bearer {self.token}"}
            else:
                login_response.failure(
                    f"Login failed with status {login_response.status_code}"
                )
                self.token = None
                self.headers = {}

    @task(10)
    def upload_video_mock(self):
  
        if not self.token:
            return

        video_content = b"0" * (10 * 1024)

        files = {"video_file": ("test_video.mp4", video_content, "video/mp4")}

        data = {"title": f"Load Test Video {random.randint(1, 100000)}"}

        with self.client.post(
            "/api/videos/upload-mock",
            files=files,
            data=data,
            headers=self.headers,
            catch_response=True,
            name="/api/videos/upload-mock",
        ) as response:
            if response.status_code == 202:
                try:
                    body = response.json()
                    vid = body.get("video_id")
                    if vid:
                        self.created_video_ids.append(vid)
                except Exception:
                    pass
                response.success()
            elif response.status_code == 401:
                response.failure("Authentication failed")
            else:
                response.failure(f"Upload failed with status {response.status_code}")

@events.init.add_listener
def on_locust_init(environment, **kwargs):
    if isinstance(environment.runner, MasterRunner):
        print("\n" + "=" * 60)
        print("LOAD TEST: Web Layer Capacity (Scenario 1)")
        print("=" * 60)
        print("Target: /api/videos/upload-mock (bypasses worker)")
        print("SLO Criteria:")
        print("  - p95 latency ≤ 1.0s")
        print("  - Error rate ≤ 5%")
        print("=" * 60 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("\n" + "=" * 60)
    print("TEST COMPLETED")
    print("=" * 60)
    print("Check Prometheus/Grafana for detailed metrics:")
    print("  - Prometheus: http://localhost:9090")
    print("  - Grafana: http://localhost:3001 (admin/admin)")
    print("=" * 60 + "\n")
