from faker import Faker

fake = Faker()

def test_signup_and_login(client):
    email = fake.unique.email()
    password = fake.password()
    r = client.post("/api/auth/signup", json={"email": email, "password": password})
    assert r.status_code in (201, 400)
    r2 = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r2.status_code == 200
    assert "access_token" in r2.json()