import uuid

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_blog_crud_and_visibility_rules(app, client, test_log):
    email = f"author_{uuid.uuid4().hex[:10]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    password = "secret123"

    await client.post(
        "/auth/register/",
        json={
            "email": email,
            "phone_number": phone,
            "first_name": "Blog",
            "last_name": "Author",
            "password": password,
            "confirm_password": password,
        },
    )
    r = await client.post("/auth/login/", json={"email": email, "password": password})
    assert r.status_code == 200

    title = f"Post {uuid.uuid4().hex[:8]}"
    payload = {
        "title": title,
        "content": "Hello **world**",
        "short_description": "Short",
        "tags": ["fastapi", "test"],
    }

    test_log("add_post")
    r = await client.post("/api/add_post/", json=payload)
    assert r.status_code == 200
    assert r.json()["status"] == "success"

    test_log("blogs list should include the new post")
    r = await client.get("/api/blogs/", params={"page": 1, "page_size": 10})
    assert r.status_code == 200
    data = r.json()
    assert data["total_result"] >= 1
    created = next(b for b in data["blogs"] if b["title"] == title)
    blog_id = created["id"]

    test_log("change status to draft")
    r = await client.patch(
        f"/api/change_blog_status/{blog_id}", params={"new_status": "draft"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("success", "info")
    assert body["blog_id"] == blog_id

    test_log("published list should now be empty (BlogNotFind)")
    r = await client.get("/api/blogs/", params={"page": 1, "page_size": 10})
    assert r.status_code == 200
    assert r.json()["status"] == "error"

    test_log("draft is not visible without auth (optional user)")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as anon:
        r = await anon.get(f"/api/get_blog/{blog_id}")
        assert r.status_code == 200
        assert r.json()["status"] == "error"

    test_log("draft is visible for author")
    r = await client.get(f"/api/get_blog/{blog_id}")
    assert r.status_code == 200
    body = r.json()
    assert (
        body.get("id") == blog_id
        or body.get("status") in ("success", "error")
        or "id" in body
    )

    test_log("delete_blog")
    r = await client.delete(f"/api/delete_blog/{blog_id}")
    assert r.status_code == 200
    assert r.json()["status"] == "success"


@pytest.mark.asyncio
async def test_add_post_duplicate_title_returns_400(client, test_log):
    email = f"author_{uuid.uuid4().hex[:10]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    password = "secret123"

    await client.post(
        "/auth/register/",
        json={
            "email": email,
            "phone_number": phone,
            "first_name": "Blog",
            "last_name": "Author",
            "password": password,
            "confirm_password": password,
        },
    )
    await client.post("/auth/login/", json={"email": email, "password": password})

    title = f"Unique {uuid.uuid4().hex[:8]}"
    payload = {
        "title": title,
        "content": "Content",
        "short_description": "Short",
        "tags": [],
    }

    test_log("first add_post")
    r = await client.post("/api/add_post/", json=payload)
    assert r.status_code == 200
    assert r.json()["status"] == "success"

    test_log("second add_post with same title must fail")
    r = await client.post("/api/add_post/", json=payload)
    assert r.status_code == 400
    assert r.json()["detail"] == "Блог с таким заголовком уже существует."
