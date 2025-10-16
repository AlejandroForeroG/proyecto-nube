def test_list_public_videos_only_processed(client, video_factory):
    v1 = video_factory.create(is_public=True, processed_path="/tmp/x1.mp4")
    v2 = video_factory.create(is_public=True, processed_path=None, status="uploaded")
    v3 = video_factory.create(is_public=False, processed_path="/tmp/x2.mp4")

    r = client.get("/api/public/videos")
    assert r.status_code == 200
    items = r.json()
    ids = {it["video_id"] for it in items}
    assert v1.video_id in ids
    assert v3.video_id not in ids
    assert all(it.get("processed_url") for it in items)


def test_vote_public_video_once_only(client, auth_headers, video_factory, vote_factory):
    v = video_factory.create(is_public=True, processed_path="/tmp/pv.mp4")
    r1 = client.post(f"/api/public/videos/{v.video_id}/vote", headers=auth_headers)
    assert r1.status_code == 200
    r2 = client.post(f"/api/public/videos/{v.video_id}/vote", headers=auth_headers)
    assert r2.status_code == 400


def test_vote_public_video_requires_auth(client, video_factory):
    v = video_factory.create(is_public=True, processed_path="/tmp/pv2.mp4")
    r = client.post(f"/api/public/videos/{v.video_id}/vote")
    assert r.status_code == 401


def test_rankings_with_and_without_city(
    client, user_factory, video_factory, vote_factory
):
    u1 = user_factory.create()
    u2 = user_factory.create(city="Bogotá")
    v1 = video_factory.create(user=u1, is_public=True)
    v2 = video_factory.create(user=u2, is_public=True)
    vote_factory.create(video=v1)
    vote_factory.create(video=v1)
    vote_factory.create(video=v2)

    r = client.get("/api/public/rankings")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 2
    assert data[0]["votes"] >= data[-1]["votes"]

    r2 = client.get("/api/public/rankings", params={"city": "Bogotá"})
    assert r2.status_code == 200
    data2 = r2.json()
    assert all(item.get("city") == "Bogotá" for item in data2)
