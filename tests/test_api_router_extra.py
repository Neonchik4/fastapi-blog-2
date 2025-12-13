import uuid

import pytest
from sqlalchemy.exc import IntegrityError


async def _register_and_login(
    client, *, email: str, phone: str, password: str = "secret123"
):
    await client.post(
        "/auth/register/",
        json={
            "email": email,
            "phone_number": phone,
            "first_name": "Api",
            "last_name": "User",
            "password": password,
            "confirm_password": password,
        },
    )
    r = await client.post("/auth/login/", json={"email": email, "password": password})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_api_blogs_returns_500_on_unhandled_exception(client, monkeypatch):
    """Endpoint: GET /api/blogs/ (ветка except -> JSONResponse 500)"""
    import app.api.router as api_router

    async def _boom(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(api_router.BlogDAO, "get_blog_list", _boom)
    r = await client.get("/api/blogs/", params={"page": 1, "page_size": 10})
    assert r.status_code == 500
    assert r.json()["detail"] == "Ошибка сервера"


@pytest.mark.asyncio
async def test_api_add_post_returns_500_on_non_unique_integrity_error(
    client, monkeypatch
):
    """Endpoint: POST /api/add_post/ (ветка IntegrityError != UNIQUE => 500)"""
    import app.api.router as api_router

    email = f"api_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)

    async def _raise_integrity(*args, **kwargs):
        raise IntegrityError("stmt", params={}, orig=Exception("some other constraint"))

    monkeypatch.setattr(api_router.BlogDAO, "add", _raise_integrity)
    r = await client.post(
        "/api/add_post/",
        json={
            "title": f"T_{uuid.uuid4().hex[:6]}",
            "content": "c",
            "short_description": "s",
            "tags": [],
        },
    )
    assert r.status_code == 500
    assert r.json()["detail"] == "Ошибка при добавлении блога."


@pytest.mark.asyncio
async def test_api_change_status_and_delete_return_400_on_dao_error(client):
    """Endpoints: PATCH /api/change_blog_status/{id}, DELETE /api/delete_blog/{id} (ветки HTTPException 400)"""
    email = f"api2_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)

    r = await client.patch(
        "/api/change_blog_status/999999", params={"new_status": "invalid"}
    )
    assert r.status_code == 400

    r = await client.delete("/api/delete_blog/999999")
    assert r.status_code == 400
