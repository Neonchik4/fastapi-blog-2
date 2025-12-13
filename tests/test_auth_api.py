import uuid

import pytest


def _user_payload(*, email: str, phone: str, password: str = "secret123") -> dict:
    return {
        "email": email,
        "phone_number": phone,
        "first_name": "Test",
        "last_name": "User",
        "password": password,
        "confirm_password": password,
    }


@pytest.mark.asyncio
async def test_register_login_me_logout_flow(client, test_log):
    email = f"u_{uuid.uuid4().hex[:10]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    password = "secret123"

    test_log(f"register user {email}")
    r = await client.post(
        "/auth/register/",
        json=_user_payload(email=email, phone=phone, password=password),
    )
    assert r.status_code == 200
    assert r.json()["message"] == "Вы успешно зарегистрированы!"

    test_log("login")
    r = await client.post("/auth/login/", json={"email": email, "password": password})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert isinstance(body["access_token"], str) and body["access_token"]

    test_log("me")
    r = await client.get("/auth/me/")
    assert r.status_code == 200
    me = r.json()
    assert me["email"] == email
    assert me["role_id"] == 1
    assert me["role_name"] == "User"

    test_log("logout")
    r = await client.get("/auth/logout/", follow_redirects=False)
    assert r.status_code == 303

    r = await client.get("/auth/me/")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_register_existing_user_returns_409(client, test_log):
    email = f"u_{uuid.uuid4().hex[:10]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"

    test_log("register first time")
    r = await client.post(
        "/auth/register/", json=_user_payload(email=email, phone=phone)
    )
    assert r.status_code == 200

    test_log("register second time (same email)")
    r = await client.post(
        "/auth/register/", json=_user_payload(email=email, phone=phone)
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "Пользователь уже существует"


@pytest.mark.asyncio
async def test_all_users_requires_admin(client, ensure_user, set_user_role, test_log):
    email = f"u_{uuid.uuid4().hex[:10]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    password = "secret123"

    user = await ensure_user(email, password=password, phone=phone)
    r = await client.post("/auth/login/", json={"email": email, "password": password})
    assert r.status_code == 200

    test_log("all_users as normal user")
    r = await client.get("/auth/all_users/")
    assert r.status_code == 403
    assert r.json()["detail"] == "Недостаточно прав!"

    test_log("promote to admin and retry")
    await set_user_role(user.id, 3)
    r = await client.get("/auth/all_users/")
    assert r.status_code == 200
    users = r.json()
    assert isinstance(users, list)
    assert any(u["email"] == email for u in users)
