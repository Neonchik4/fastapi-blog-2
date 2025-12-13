import uuid

import pytest


@pytest.mark.asyncio
async def test_likes_toggle_and_queries(client, likes_file, test_log):
    email = f"liker_{uuid.uuid4().hex[:10]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    password = "secret123"

    await client.post(
        "/auth/register/",
        json={
            "email": email,
            "phone_number": phone,
            "first_name": "Like",
            "last_name": "User",
            "password": password,
            "confirm_password": password,
        },
    )
    r = await client.post("/auth/login/", json={"email": email, "password": password})
    assert r.status_code == 200

    me = (await client.get("/auth/me/")).json()
    user_id = me["id"]

    post_id = 123

    test_log("toggle like on")
    r = await client.post("/api/likes/toggle", json={"post_id": post_id, "liked": True})
    assert r.status_code == 200
    assert r.json() == {"user_id": user_id, "post_id": post_id, "liked": True}

    test_log("is liked by user => True")
    r = await client.get(f"/api/likes/user/{user_id}/post/{post_id}")
    assert r.status_code == 200
    assert r.json() is True

    test_log("user likes list contains our like")
    r = await client.get(f"/api/likes/user/{user_id}")
    assert r.status_code == 200
    likes = r.json()
    assert any(
        like_item["post_id"] == post_id and like_item["liked"] is True
        for like_item in likes
    )

    test_log("toggle like off (second toggle removes record)")
    r = await client.post("/api/likes/toggle", json={"post_id": post_id, "liked": True})
    assert r.status_code == 200
    assert r.json() == {"user_id": user_id, "post_id": post_id, "liked": False}

    test_log("is liked by user => False")
    r = await client.get(f"/api/likes/user/{user_id}/post/{post_id}")
    assert r.status_code == 200
    assert r.json() is False
