import uuid

import pytest


@pytest.mark.asyncio
async def test_toggle_like_existing_like_toggle_off(client, likes_file):
    """Тест: toggle_like для существующего лайка с liked=False -> удаляет запись"""
    email = f"toggle_off_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"

    await client.post(
        "/auth/register/",
        json={
            "email": email,
            "phone_number": phone,
            "first_name": "Toggle",
            "last_name": "Off",
            "password": "secret123",
            "confirm_password": "secret123",
        },
    )
    login_r = await client.post(
        "/auth/login/", json={"email": email, "password": "secret123"}
    )
    assert login_r.status_code == 200
    assert "users_access_token" in login_r.cookies

    me_r = await client.get("/auth/me/")
    assert me_r.status_code == 200
    me = me_r.json()
    user_id = me["id"]
    post_id = 123

    # Создаём лайк
    r = await client.post("/api/likes/toggle", json={"post_id": post_id, "liked": True})
    assert r.status_code == 200
    assert r.json()["liked"] is True

    r = await client.post(
        "/api/likes/toggle", json={"post_id": post_id, "liked": False}
    )
    assert r.status_code == 200
    assert r.json()["liked"] is False

    # Проверяем, что лайк удалён
    r = await client.get(f"/api/likes/user/{user_id}/post/{post_id}")
    assert r.status_code == 200
    assert r.json() is False


@pytest.mark.asyncio
async def test_toggle_like_existing_like_toggle_on(client, likes_file, ensure_user):
    """Тест: toggle_like для существующего лайка с liked=True -> переключает на False"""
    email = f"toggle_on_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"

    await ensure_user(
        email=email,
        password="secret123",
        phone=phone,
        first_name="Toggle",
        last_name="John",
    )

    login_r = await client.post(
        "/auth/login/", json={"email": email, "password": "secret123"}
    )
    assert login_r.status_code == 200
    assert "users_access_token" in login_r.cookies

    me_r = await client.get("/auth/me/")
    assert me_r.status_code == 200
    post_id = 456

    r = await client.post(
        "/api/likes/toggle", json={"post_id": post_id, "liked": False}
    )
    assert r.status_code == 200
    assert r.json()["liked"] is False

    r = await client.post("/api/likes/toggle", json={"post_id": post_id, "liked": True})
    assert r.status_code == 200
    assert r.json()["liked"] is True

    # Переключаем существующий лайк
    r = await client.post("/api/likes/toggle", json={"post_id": post_id, "liked": True})
    assert r.status_code == 200
    assert r.json()["liked"] is False


@pytest.mark.asyncio
async def test_get_user_likes_filters_by_liked_true(client, likes_file):
    """Тест: get_user_likes возвращает только записи с liked=True"""
    email = f"user_likes_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"

    await client.post(
        "/auth/register/",
        json={
            "email": email,
            "phone_number": phone,
            "first_name": "User",
            "last_name": "Likes",
            "password": "secret123",
            "confirm_password": "secret123",
        },
    )
    login_r = await client.post(
        "/auth/login/", json={"email": email, "password": "secret123"}
    )
    assert login_r.status_code == 200
    assert "users_access_token" in login_r.cookies

    me_r = await client.get("/auth/me/")
    assert me_r.status_code == 200
    me = me_r.json()
    user_id = me["id"]

    # Создаём лайки
    r = await client.post("/api/likes/toggle", json={"post_id": 1, "liked": True})
    assert r.status_code == 200
    r = await client.post("/api/likes/toggle", json={"post_id": 2, "liked": True})
    assert r.status_code == 200

    # Получаем все лайки пользователя
    r = await client.get(f"/api/likes/user/{user_id}")
    assert r.status_code == 200
    likes = r.json()
    assert isinstance(likes, list)
    assert all(like["liked"] is True for like in likes)
    assert all(like["user_id"] == user_id for like in likes)


@pytest.mark.asyncio
async def test_get_post_likes_filters_by_liked_true(client, likes_file):
    """Тест: get_post_likes возвращает только записи с liked=True"""
    email1 = f"post_likes1_{uuid.uuid4().hex[:8]}@example.com"
    email2 = f"post_likes2_{uuid.uuid4().hex[:8]}@example.com"
    phone1 = f"+7{uuid.uuid4().int % 10**10:010d}"
    phone2 = f"+7{uuid.uuid4().int % 10**10:010d}"

    # Регистрируем двух пользователей
    await client.post(
        "/auth/register/",
        json={
            "email": email1,
            "phone_number": phone1,
            "first_name": "Post",
            "last_name": "Likes1",
            "password": "secret123",
            "confirm_password": "secret123",
        },
    )
    await client.post(
        "/auth/register/",
        json={
            "email": email2,
            "phone_number": phone2,
            "first_name": "Post",
            "last_name": "Likes2",
            "password": "secret123",
            "confirm_password": "secret123",
        },
    )

    post_id = 789

    # Первый пользователь лайкает
    await client.post("/auth/login/", json={"email": email1, "password": "secret123"})
    r = await client.post("/api/likes/toggle", json={"post_id": post_id, "liked": True})
    assert r.status_code == 200

    # Второй пользователь лайкает
    await client.post("/auth/login/", json={"email": email2, "password": "secret123"})
    r = await client.post("/api/likes/toggle", json={"post_id": post_id, "liked": True})
    assert r.status_code == 200

    # Получаем все лайки поста
    r = await client.get(f"/api/likes/post/{post_id}")
    assert r.status_code == 200
    likes = r.json()
    assert isinstance(likes, list)
    assert len(likes) == 2
    assert all(like["post_id"] == post_id for like in likes)
    assert all(like["liked"] is True for like in likes)


@pytest.mark.asyncio
async def test_is_post_liked_by_user_returns_false_when_not_liked(client, likes_file):
    """Тест: is_post_liked_by_user возвращает False когда пост не лайкнут"""
    email = f"not_liked_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"

    await client.post(
        "/auth/register/",
        json={
            "email": email,
            "phone_number": phone,
            "first_name": "Not",
            "last_name": "Liked",
            "password": "secret123",
            "confirm_password": "secret123",
        },
    )
    login_r = await client.post(
        "/auth/login/", json={"email": email, "password": "secret123"}
    )
    assert login_r.status_code == 200
    assert "users_access_token" in login_r.cookies

    me_r = await client.get("/auth/me/")
    assert me_r.status_code == 200
    me = me_r.json()
    user_id = me["id"]
    post_id = 999

    # Проверяем нелайкнутый пост
    r = await client.get(f"/api/likes/user/{user_id}/post/{post_id}")
    assert r.status_code == 200
    assert r.json() is False


@pytest.mark.asyncio
async def test_is_post_liked_by_user_returns_true_when_liked(
    client, likes_file, ensure_user
):
    """Тест: is_post_liked_by_user возвращает True когда пост лайкнут"""
    email = f"is_liked_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"

    await ensure_user(
        email=email,
        password="secret123",
        phone=phone,
        first_name="Ivan",
        last_name="Liked",
    )

    login_r = await client.post(
        "/auth/login/", json={"email": email, "password": "secret123"}
    )
    assert login_r.status_code == 200
    assert "users_access_token" in login_r.cookies

    me_r = await client.get("/auth/me/")
    assert me_r.status_code == 200
    me = me_r.json()
    user_id = me["id"]
    post_id = 888

    # Лайкаем пост
    r = await client.post("/api/likes/toggle", json={"post_id": post_id, "liked": True})
    assert r.status_code == 200
    assert r.json()["liked"] is True

    # Проверяем, что пост лайкнут
    r = await client.get(f"/api/likes/user/{user_id}/post/{post_id}")
    assert r.status_code == 200
    assert r.json() is True
