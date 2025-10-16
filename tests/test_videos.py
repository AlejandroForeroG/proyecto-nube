from io import BytesIO

from app.models import VideoStatus


def test_upload_video_creates_record(client, auth_headers):
    content = b"0" * 1024
    files = {"video_file": ("demo.mp4", BytesIO(content), "video/mp4")}
    data = {"title": "My Skills"}
    r = client.post("/api/videos/upload", files=files, data=data, headers=auth_headers)
    assert r.status_code == 201
    body = r.json()
    assert body["message"].startswith("Video subido correctamente")
    assert body["task_id"]


def test_upload_video_invalid_type(client, auth_headers):
    files = {"video_file": ("bad.txt", BytesIO(b"hi"), "text/plain")}
    data = {"title": "My Skills"}
    r = client.post("/api/videos/upload", files=files, data=data, headers=auth_headers)
    assert r.status_code == 400


def test_get_user_videos_lists_processed(
    client, auth_headers, video_factory, auth_user
):
    v1 = video_factory.create(
        user=auth_user, status=VideoStatus.done.value, processed_path="/tmp/p1.mp4"
    )
    video_factory.create(user=auth_user, status=VideoStatus.uploaded.value)
    video_factory.create(status=VideoStatus.done.value, processed_path="/tmp/p2.mp4")

    r = client.get("/api/videos", headers=auth_headers)
    assert r.status_code == 200
    items = r.json()
    assert isinstance(items, list)
    ids = {it["video_id"] for it in items}
    assert v1.video_id in ids
    assert len(items) == 1


def test_video_detail_includes_urls_and_votes(
    client, auth_headers, video_factory, vote_factory, auth_user
):
    v = video_factory.create(
        user=auth_user, status=VideoStatus.done.value, processed_path="/tmp/p3.mp4"
    )
    vote_factory.create(user=auth_user, video=v)

    r = client.get(f"/api/videos/{v.video_id}", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["video_id"] == v.video_id
    assert body["votes"] >= 1


def test_delete_video_success(client, auth_headers, video_factory, auth_user):
    v = video_factory.create(user=auth_user, status=VideoStatus.uploaded.value)
    r = client.delete(f"/api/videos/{v.video_id}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["video_id"] == v.video_id


def test_delete_video_forbidden_other_user(
    client, user_factory, make_auth_headers, video_factory
):
    v = video_factory.create()
    other_user = user_factory.create()
    headers = make_auth_headers(other_user.id)
    r = client.delete(f"/api/videos/{v.video_id}", headers=headers)
    assert r.status_code == 403


def test_delete_video_bad_request_if_public(
    client, auth_headers, video_factory, auth_user
):
    v = video_factory.create(
        user=auth_user, status=VideoStatus.done.value, is_public=True
    )
    r = client.delete(f"/api/videos/{v.video_id}", headers=auth_headers)
    assert r.status_code == 400
