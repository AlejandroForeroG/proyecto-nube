import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import engine, get_db
from app.core.security import create_access_token
from app.main import app
from tests.factories import UserFactory, VideoFactory, VoteFactory


@pytest.fixture
def db_session():
    connection = engine.connect()
    trans = connection.begin()
    TestingSessionLocal = sessionmaker(bind=connection, expire_on_commit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _override_settings_and_fs(tmp_path, monkeypatch):
    settings.TESTING = True
    uploads_dir = tmp_path / "uploads"
    processed_dir = tmp_path / "processed"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    settings.UPLOAD_PATH = str(uploads_dir)
    settings.PROCESSED_PATH = str(processed_dir)
    monkeypatch.setenv("CELERY_EAGER", "1")
    yield


@pytest.fixture(autouse=True)
def _mock_celery_delay(monkeypatch):
    from app.api.routes import videos as videos_module

    class DummyResult:
        def __init__(self, id: str):
            self.id = id

    def fake_delay(video_db_id: int, original_path: str):
        return DummyResult("test-task-id")

    monkeypatch.setattr(videos_module.process_video_task, "delay", fake_delay)
    yield


@pytest.fixture
def user_factory(db_session):
    return UserFactory(db_session)


@pytest.fixture
def video_factory(db_session):
    return VideoFactory(db_session)


@pytest.fixture
def vote_factory(db_session):
    return VoteFactory(db_session)


@pytest.fixture
def auth_user(user_factory):
    user = user_factory.create()
    return user


@pytest.fixture
def auth_headers(auth_user):
    token = create_access_token({"sub": str(auth_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def make_auth_headers():
    def _make(user_id: int) -> dict[str, str]:
        token = create_access_token({"sub": str(user_id)})
        return {"Authorization": f"Bearer {token}"}

    return _make
