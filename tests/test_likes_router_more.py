import builtins

import pytest


def test_read_likes_missing_and_invalid_json(tmp_path, monkeypatch):
    import app.api.likes_router as likes_router

    monkeypatch.setattr(likes_router, "LIKES_FILE", tmp_path / "nope.json")
    assert likes_router.read_likes() == []

    p = tmp_path / "likes.json"
    p.write_text("{", encoding="utf-8")
    monkeypatch.setattr(likes_router, "LIKES_FILE", p)
    assert likes_router.read_likes() == []


def test_write_likes_open_failure_raises_http_500(tmp_path, monkeypatch):
    from fastapi import HTTPException

    import app.api.likes_router as likes_router

    p = tmp_path / "likes.json"
    monkeypatch.setattr(likes_router, "LIKES_FILE", p)

    real_open = builtins.open

    def _fake_open(file, mode="r", *args, **kwargs):
        if str(file) == str(p) and "w" in mode:
            raise OSError("disk full")
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", _fake_open)
    with pytest.raises(HTTPException) as e:
        likes_router.write_likes([{"user_id": 1, "post_id": 2, "liked": True}])
    assert e.value.status_code == 500
    assert e.value.detail == "Failed to save like"


@pytest.mark.asyncio
async def test_toggle_like_liked_false_does_not_create_record(client, likes_file):
    await client.post(
        "/auth/register/",
        json={
            "email": "like_false@example.com",
            "phone_number": "+70000000222",
            "first_name": "Like",
            "last_name": "False",
            "password": "secret123",
            "confirm_password": "secret123",
        },
    )
    r = await client.post(
        "/auth/login/",
        json={"email": "like_false@example.com", "password": "secret123"},
    )
    assert r.status_code == 200

    me = (await client.get("/auth/me/")).json()
    user_id = me["id"]

    r = await client.post("/api/likes/toggle", json={"post_id": 77, "liked": False})
    assert r.status_code == 200
    assert r.json() == {"user_id": user_id, "post_id": 77, "liked": False}

    assert likes_file.read_text(encoding="utf-8").strip().startswith("[")


@pytest.mark.asyncio
async def test_toggle_like_write_failure_returns_500(client, monkeypatch):
    from fastapi import HTTPException

    import app.api.likes_router as likes_router

    await client.post(
        "/auth/register/",
        json={
            "email": "like_write_fail@example.com",
            "phone_number": "+70000000223",
            "first_name": "Like",
            "last_name": "Fail",
            "password": "secret123",
            "confirm_password": "secret123",
        },
    )
    r = await client.post(
        "/auth/login/",
        json={"email": "like_write_fail@example.com", "password": "secret123"},
    )
    assert r.status_code == 200

    def _boom(*args, **kwargs):
        raise HTTPException(status_code=500, detail="Failed to save like")

    monkeypatch.setattr(likes_router, "write_likes", _boom)
    r = await client.post("/api/likes/toggle", json={"post_id": 1, "liked": True})
    assert r.status_code == 500
    assert r.json()["detail"] == "Failed to save like"
