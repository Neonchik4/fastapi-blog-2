import uuid

import pytest


@pytest.mark.asyncio
async def test_auth_user_wrong_password_raises_exception(client):
    """Тест: POST /auth/login/ с неверным паролем -> IncorrectEmailOrPasswordException"""
    email = f"wrong_pwd_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"

    await client.post(
        "/auth/register/",
        json={
            "email": email,
            "phone_number": phone,
            "first_name": "Wrong",
            "last_name": "Password",
            "password": "secret123",
            "confirm_password": "secret123",
        },
    )

    r = await client.post(
        "/auth/login/", json={"email": email, "password": "wrongpassword"}
    )
    assert r.status_code == 401
    # Проверяем реальный текст ошибки из exceptions.py
    assert "Неверная почта или пароль" in r.json()["detail"]


@pytest.mark.asyncio
async def test_logout_get_and_post_methods(client):
    """Тест: GET и POST /auth/logout/ оба работают"""
    email = f"logout_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"

    await client.post(
        "/auth/register/",
        json={
            "email": email,
            "phone_number": phone,
            "first_name": "Logout",
            "last_name": "User",
            "password": "secret123",
            "confirm_password": "secret123",
        },
    )
    await client.post("/auth/login/", json={"email": email, "password": "secret123"})

    # GET метод
    r = await client.get("/auth/logout/", follow_redirects=False)
    assert r.status_code == 303
    assert (
        "users_access_token" not in r.cookies
        or r.cookies.get("users_access_token") == ""
    )

    # POST метод
    await client.post("/auth/login/", json={"email": email, "password": "secret123"})
    r = await client.post("/auth/logout/", follow_redirects=False)
    assert r.status_code == 303
    assert (
        "users_access_token" not in r.cookies
        or r.cookies.get("users_access_token") == ""
    )


@pytest.mark.asyncio
async def test_get_me_returns_user_info_with_computed_fields(client, ensure_user):
    """Тест: GET /auth/me/ возвращает пользователя с computed fields"""
    email = f"me_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"

    # Используем ensure_user для гарантированного создания пользователя
    await ensure_user(
        email=email,
        password="secret123",
        phone=phone,
        first_name="Max",
        last_name="User",
    )

    login_r = await client.post(
        "/auth/login/", json={"email": email, "password": "secret123"}
    )
    assert login_r.status_code == 200
    # Проверяем, что cookie установлен в ответе
    # httpx автоматически сохраняет cookies между запросами
    assert "users_access_token" in login_r.cookies

    # httpx.AsyncClient автоматически передает cookies в следующий запрос
    r = await client.get("/auth/me/")
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == email
    assert "role_id" in data
    assert "role_name" in data
    assert data["role_id"] == 1  # Default role
    assert data["role_name"] == "User"


@pytest.mark.asyncio
async def test_register_user_validation_error_returns_422(client):
    """Тест: POST /auth/register/ с невалидными данными -> 422"""
    # Несовпадающие пароли
    r = await client.post(
        "/auth/register/",
        json={
            "email": f"val_{uuid.uuid4().hex[:8]}@example.com",
            "phone_number": f"+7{uuid.uuid4().int % 10**10:010d}",
            "first_name": "Val",
            "last_name": "Error",
            "password": "secret123",
            "confirm_password": "different",
        },
    )
    assert r.status_code == 422
