from faker import Faker

fake = Faker()


def _signup_payload(email: str, password: str) -> dict:
    return {
        "email": email,
        "password1": password,
        "password2": password,
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "city": fake.city(),
        "country": fake.country(),
    }


def test_signup_and_login_json(client):
    email = fake.unique.email()
    password = fake.password()
    r = client.post("/api/auth/signup", json=_signup_payload(email, password))
    assert r.status_code == 201
    assert {"id", "email"}.issubset(r.json().keys())

    r2 = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r2.status_code == 200
    data = r2.json()
    assert "access_token" in data and data.get("token_type") == "bearer"


def test_signup_duplicate_email(client):
    email = fake.unique.email()
    password = fake.password()
    r1 = client.post("/api/auth/signup", json=_signup_payload(email, password))
    assert r1.status_code == 201
    r2 = client.post("/api/auth/signup", json=_signup_payload(email, password))
    assert r2.status_code == 400


def test_login_invalid_credentials(client):
    r = client.post("/api/auth/login", json={"email": fake.email(), "password": "bad"})
    assert r.status_code == 401
