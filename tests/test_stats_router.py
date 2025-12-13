import uuid

import pytest


@pytest.mark.asyncio
async def test_stats_page_requires_auth(client):
    """Тест: GET /stats/ требует авторизации"""
    # get_current_user выбрасывает HTTPException при отсутствии токена
    r = await client.get("/stats/", follow_redirects=False)
    # Может быть 401 (HTTPException) или редирект
    assert r.status_code in (401, 302, 303)


@pytest.mark.asyncio
async def test_stats_page_renders_html(client):
    """Тест: GET /stats/ возвращает HTML со статистикой"""
    email = f"stats_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"

    await client.post(
        "/auth/register/",
        json={
            "email": email,
            "phone_number": phone,
            "first_name": "Stats",
            "last_name": "User",
            "password": "secret123",
            "confirm_password": "secret123",
        },
    )
    await client.post("/auth/login/", json={"email": email, "password": "secret123"})

    r = await client.get("/stats/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "").lower()
    # Проверяем наличие ключевых элементов статистики в HTML
    text = r.text
    assert "Статистика" in text or "статистика" in text or "users_total" in text


@pytest.mark.asyncio
async def test_stats_api_returns_json(client):
    """Тест: GET /api/stats/ возвращает JSON"""
    email = f"stats_api_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"

    await client.post(
        "/auth/register/",
        json={
            "email": email,
            "phone_number": phone,
            "first_name": "Stats",
            "last_name": "API",
            "password": "secret123",
            "confirm_password": "secret123",
        },
    )
    await client.post("/auth/login/", json={"email": email, "password": "secret123"})

    r = await client.get("/api/stats/")
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/json")
    data = r.json()
    assert data["ok"] is True
    assert "stats" in data
    stats = data["stats"]
    assert "users_total" in stats
    assert "blogs_total" in stats
    assert "tags_total" in stats
    assert "likes_total" in stats
