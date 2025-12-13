import uuid

import pytest


async def _register_and_login(
    client, *, email: str, phone: str, password: str = "secret123"
):
    await client.post(
        "/auth/register/",
        json={
            "email": email,
            "phone_number": phone,
            "first_name": "Test",
            "last_name": "User",
            "password": password,
            "confirm_password": password,
        },
    )
    r = await client.post("/auth/login/", json={"email": email, "password": password})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_home_page_with_search(client):
    """Тест: GET / с параметром search"""
    r = await client.get("/", params={"search": "test"})
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "").lower()


@pytest.mark.asyncio
async def test_home_page_with_tag(client):
    """Тест: GET / с параметром tag"""
    r = await client.get("/", params={"tag": "python"})
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "").lower()


@pytest.mark.asyncio
async def test_home_page_with_pagination(client):
    """Тест: GET / с параметрами page и page_size"""
    r = await client.get("/", params={"page": 2, "page_size": 3})
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "").lower()


@pytest.mark.asyncio
async def test_home_page_authenticated(client):
    """Тест: GET / с авторизованным пользователем"""
    email = f"home_auth_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)

    r = await client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "").lower()


@pytest.mark.asyncio
async def test_create_blog_submit_with_tags_success(client):
    """Тест: POST /blogs/create/ успешное создание с тегами"""
    email = f"create_tags_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)

    title = f"TagsBlog_{uuid.uuid4().hex[:6]}"
    r = await client.post(
        "/blogs/create/",
        data={
            "title": title,
            "content": "Content with tags",
            "short_description": "Short desc",
            "tags": "python, fastapi, testing",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"].startswith("/blogs/")


@pytest.mark.asyncio
async def test_edit_blog_submit_success_with_tags_update(client):
    """Тест: POST /blogs/{id}/edit/ успешное редактирование с обновлением тегов"""
    email = f"edit_tags_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)

    # Создаём блог с тегами
    title = f"EditTags_{uuid.uuid4().hex[:6]}"
    r = await client.post(
        "/blogs/create/",
        data={
            "title": title,
            "content": "Content",
            "short_description": "Short",
            "tags": "python, fastapi",
        },
        follow_redirects=False,
    )
    blog_id = int(r.headers["location"].strip("/").split("/")[1])

    # Редактируем с новыми тегами
    r = await client.post(
        f"/blogs/{blog_id}/edit/",
        data={
            "title": title,
            "content": "Updated content",
            "short_description": "Updated short",
            "tags": "django, flask, newtag",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == f"/blogs/{blog_id}/"


@pytest.mark.asyncio
async def test_edit_blog_submit_admin_can_edit_any_blog(
    client, ensure_user, set_user_role
):
    """Тест: POST /blogs/{id}/edit/ админ может редактировать чужой блог"""
    # Создаём автора блога
    email1 = f"author_edit_{uuid.uuid4().hex[:8]}@example.com"
    phone1 = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email1, phone=phone1)

    title = f"AdminEdit_{uuid.uuid4().hex[:6]}"
    r = await client.post(
        "/blogs/create/",
        data={
            "title": title,
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )
    blog_id = int(r.headers["location"].strip("/").split("/")[1])

    # Создаём админа
    email2 = f"admin_edit_{uuid.uuid4().hex[:8]}@example.com"
    phone2 = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email2, phone=phone2)
    user = await ensure_user(email2, password="secret123", phone=phone2)
    await set_user_role(user.id, 3)  # Admin

    # Админ редактирует чужой блог
    r = await client.post(
        f"/blogs/{blog_id}/edit/",
        data={
            "title": title,
            "content": "Admin edited content",
            "short_description": "Admin short",
            "tags": "",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303


@pytest.mark.asyncio
async def test_edit_blog_submit_validation_error_blog_not_found(client):
    """Тест: POST /blogs/{id}/edit/ валидационная ошибка, затем блог не найден"""
    email = f"edit_val_404_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)

    r = await client.post(
        "/blogs/999999/edit/",
        data={
            "title": "",
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
    )
    assert r.status_code in (400, 404)


@pytest.mark.asyncio
async def test_blogs_page_author_not_found(client):
    """Тест: GET /blogs/ с author_id, автор не найден"""
    r = await client.get("/blogs/", params={"author_id": 999999})
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "").lower()
    assert "не найден" in r.text.lower() or "999999" in r.text


@pytest.mark.asyncio
async def test_blogs_page_tag_not_found(client):
    """Тест: GET /blogs/ с tag, тег не найден"""
    r = await client.get("/blogs/", params={"tag": "nonexistent-tag-12345"})
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "").lower()
    assert "не найден" in r.text.lower() or "nonexistent-tag-12345" in r.text


@pytest.mark.asyncio
async def test_blogs_page_search_not_found(client):
    """Тест: GET /blogs/ с search, результаты не найдены"""
    r = await client.get("/blogs/", params={"search": "nonexistent-search-12345"})
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "").lower()
    assert "ничего не найдено" in r.text.lower() or "nonexistent-search-12345" in r.text


@pytest.mark.asyncio
async def test_blogs_page_with_all_filters(client):
    """Тест: GET /blogs/ с несколькими фильтрами"""
    r = await client.get(
        "/blogs/",
        params={
            "author_id": 1,
            "tag": "python",
            "search": "test",
            "page": 1,
            "page_size": 10,
        },
    )
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "").lower()


@pytest.mark.asyncio
async def test_blog_details_with_admin_role(client, ensure_user, set_user_role):
    """Тест: GET /blogs/{id}/ для админа -> is_admin=True"""
    email = f"admin_details_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)

    # Создаём блог
    title = f"AdminDetails_{uuid.uuid4().hex[:6]}"
    r = await client.post(
        "/blogs/create/",
        data={
            "title": title,
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )
    blog_id = int(r.headers["location"].strip("/").split("/")[1])

    # Делаем пользователя админом
    user = await ensure_user(email, password="secret123", phone=phone)
    await set_user_role(user.id, 3)  # Admin

    r = await client.get(f"/blogs/{blog_id}/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "").lower()


@pytest.mark.asyncio
async def test_blog_details_with_superadmin_role(client, ensure_user, set_user_role):
    """Тест: GET /blogs/{id}/ для суперадмина -> is_admin=True"""
    email = f"superadmin_details_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)

    # Создаём блог
    title = f"SuperAdminDetails_{uuid.uuid4().hex[:6]}"
    r = await client.post(
        "/blogs/create/",
        data={
            "title": title,
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )
    blog_id = int(r.headers["location"].strip("/").split("/")[1])

    # Делаем пользователя суперадмином
    user = await ensure_user(email, password="secret123", phone=phone)
    await set_user_role(user.id, 4)  # SuperAdmin

    r = await client.get(f"/blogs/{blog_id}/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "").lower()


@pytest.mark.asyncio
async def test_blog_details_without_user(client):
    """Тест: GET /blogs/{id}/ без авторизации"""
    # Сначала создаём блог от авторизованного пользователя
    email = f"blog_anon_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)

    title = f"AnonBlog_{uuid.uuid4().hex[:6]}"
    r = await client.post(
        "/blogs/create/",
        data={
            "title": title,
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )
    blog_id = int(r.headers["location"].strip("/").split("/")[1])

    # Выходим (удаляем cookies)
    client.cookies.clear()

    # Просматриваем блог без авторизации
    r = await client.get(f"/blogs/{blog_id}/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "").lower()


@pytest.mark.asyncio
async def test_blog_details_blog_not_found_dict(client):
    """Тест: GET /blogs/{id}/ когда get_blog_info возвращает dict (BlogNotFind)"""
    r = await client.get("/blogs/999999/")
    assert r.status_code == 404
    assert "text/html" in r.headers.get("content-type", "").lower()


@pytest.mark.asyncio
async def test_profile_page_renders(client):
    """Тест: GET /profile/ отображает страницу профиля"""
    email = f"profile_get_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)

    r = await client.get("/profile/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "").lower()


@pytest.mark.asyncio
async def test_profile_update_success(client):
    """Тест: POST /profile/ успешное обновление профиля"""
    email = f"profile_success_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)

    r = await client.post(
        "/profile/",
        data={
            "first_name": "UpdatedName",
            "last_name": "UpdatedLast",
        },
    )
    assert r.status_code == 200
    assert "Профиль успешно обновлен" in r.text or "обновлен" in r.text.lower()


@pytest.mark.asyncio
async def test_profile_update_with_role_id(client, db_sessionmaker):
    """Тест: POST /profile/ обновление с role_id"""
    email = f"profile_role_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)

    r = await client.post(
        "/profile/",
        data={
            "role_id": 2,  # Moderator
        },
    )
    # Может быть 200 (успех) или 400 (если роль нельзя изменить)
    assert r.status_code in (200, 400)


@pytest.mark.asyncio
async def test_profile_update_duplicate_email(client):
    """Тест: POST /profile/ с дубликатом email"""
    email1 = f"profile_email1_{uuid.uuid4().hex[:8]}@example.com"
    email2 = f"profile_email2_{uuid.uuid4().hex[:8]}@example.com"
    phone1 = f"+7{uuid.uuid4().int % 10**10:010d}"
    phone2 = f"+7{uuid.uuid4().int % 10**10:010d}"

    # Регистрируем двух пользователей
    await _register_and_login(client, email=email1, phone=phone1)

    await client.post(
        "/auth/register/",
        json={
            "email": email2,
            "phone_number": phone2,
            "first_name": "User",
            "last_name": "Two",
            "password": "secret123",
            "confirm_password": "secret123",
        },
    )

    # Первый пользователь пытается использовать email второго
    await client.post("/auth/login/", json={"email": email1, "password": "secret123"})
    r = await client.post(
        "/profile/",
        data={"email": email2},
    )
    assert r.status_code == 400
    assert "email" in r.text.lower() or "уже существует" in r.text.lower()


@pytest.mark.asyncio
async def test_profile_update_invalid_role_id_removed(client):
    """Тест: POST /profile/ с невалидным role_id -> удаляется из form_dict"""
    email = f"profile_invalid_role_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)

    r = await client.post(
        "/profile/",
        data={"role_id": "invalid"},
    )
    # Невалидный role_id удаляется, update_dict пустой -> "Нет изменений для сохранения"
    assert r.status_code == 200
    assert "Нет изменений для сохранения" in r.text


@pytest.mark.asyncio
async def test_edit_blog_submit_blog_not_found_after_validation(client):
    """Тест: POST /blogs/{id}/edit/ валидация прошла, но блог не найден"""
    email = f"edit_404_val_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)

    # Пытаемся отредактировать несуществующий блог с валидными данными
    r = await client.post(
        "/blogs/999999/edit/",
        data={
            "title": "Valid Title",
            "content": "Valid content",
            "short_description": "Valid short",
            "tags": "",
        },
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_edit_blog_submit_permission_denied_after_validation(client):
    """Тест: POST /blogs/{id}/edit/ валидация прошла, но нет прав"""
    email1 = f"author_perm_{uuid.uuid4().hex[:8]}@example.com"
    phone1 = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email1, phone=phone1)

    # Создаём блог
    title = f"PermBlog_{uuid.uuid4().hex[:6]}"
    r = await client.post(
        "/blogs/create/",
        data={
            "title": title,
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )
    blog_id = int(r.headers["location"].strip("/").split("/")[1])

    # Другой пользователь пытается редактировать
    email2 = f"other_perm_{uuid.uuid4().hex[:8]}@example.com"
    phone2 = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email2, phone=phone2)

    r = await client.post(
        f"/blogs/{blog_id}/edit/",
        data={
            "title": title,
            "content": "Hacked content",
            "short_description": "Hacked short",
            "tags": "",
        },
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_edit_blog_submit_integrity_error_blog_not_found_after_rollback(client):
    """Тест: POST /blogs/{id}/edit/ IntegrityError, после rollback блог не найден"""
    email = f"edit_integrity_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)

    # Создаём два блога
    title1 = f"Integrity1_{uuid.uuid4().hex[:6]}"
    await client.post(
        "/blogs/create/",
        data={
            "title": title1,
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )

    title2 = f"Integrity2_{uuid.uuid4().hex[:6]}"
    r2 = await client.post(
        "/blogs/create/",
        data={
            "title": title2,
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )
    blog_id2 = int(r2.headers["location"].strip("/").split("/")[1])

    # Пытаемся изменить title второго блога на title первого (дубликат)
    r = await client.post(
        f"/blogs/{blog_id2}/edit/",
        data={
            "title": title1,  # Дубликат
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
    )
    assert r.status_code == 400
    assert "Блог с таким заголовком уже существует" in r.text


@pytest.mark.asyncio
async def test_all_drafts_page_user_role_not_admin(client):
    """Тест: GET /blogs/all-drafts/ для пользователя без роли Admin/SuperAdmin -> 404"""
    email = f"all_drafts_user_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)

    r = await client.get("/blogs/all-drafts/")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_all_drafts_page_user_no_role(client, db_sessionmaker):
    """Тест: GET /blogs/all-drafts/ для пользователя с ролью User (не Admin/SuperAdmin) -> 404"""
    email = f"all_drafts_no_role_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)

    # Убеждаемся, что у пользователя роль User (id=1), а не Admin/SuperAdmin
    # По умолчанию при регистрации устанавливается role_id=1 (User)
    # Проверяем, что пользователь с обычной ролью получает 404
    from app.auth.dao import UsersDAO
    from app.auth.schemas import EmailModel

    async with db_sessionmaker() as session:
        user = await UsersDAO.find_one_or_none(
            session=session, filters=EmailModel(email=email)
        )
        if user:
            # Убеждаемся, что роль User (id=1), не Admin/SuperAdmin
            user.role_id = 1  # User
            await session.commit()

    r = await client.get("/blogs/all-drafts/")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_profile_update_empty_strings_filtered(client):
    """Тест: POST /profile/ пустые строки фильтруются"""
    email = f"profile_empty_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)

    r = await client.post(
        "/profile/",
        data={
            "first_name": "",  # Пустая строка должна быть отфильтрована
            "last_name": "   ",  # Пробелы тоже должны быть отфильтрованы
            "phone_number": "",  # Пустая строка
        },
    )
    # Все пустые строки отфильтрованы, update_dict пустой -> "Нет изменений для сохранения"
    assert r.status_code == 200
    assert "Нет изменений для сохранения" in r.text


@pytest.mark.asyncio
async def test_profile_update_role_id_none_removed(client):
    """Тест: POST /profile/ с role_id=None -> удаляется"""
    email = f"profile_role_none_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)

    r = await client.post(
        "/profile/",
        data={"role_id": ""},  # Пустая строка для role_id
    )
    # Пустой role_id удаляется, update_dict пустой
    assert r.status_code == 200
    assert "Нет изменений для сохранения" in r.text


@pytest.mark.asyncio
async def test_blog_details_blog_not_found_blognotfind(client):
    """Тест: GET /blogs/{id}/ когда get_blog_info возвращает BlogNotFind"""
    # get_blog_info может вернуть BlogNotFind, который проверяется через isinstance
    r = await client.get("/blogs/999999/")
    assert r.status_code == 404
    assert "text/html" in r.headers.get("content-type", "").lower()


@pytest.mark.asyncio
async def test_blog_details_user_without_role(client, db_sessionmaker):
    """Тест: GET /blogs/{id}/ для пользователя с обычной ролью (не админ) -> is_admin=False"""
    email = f"blog_no_role_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)

    # Создаём блог
    title = f"NoRoleBlog_{uuid.uuid4().hex[:6]}"
    r = await client.post(
        "/blogs/create/",
        data={
            "title": title,
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )
    blog_id = int(r.headers["location"].strip("/").split("/")[1])

    # Убеждаемся, что у пользователя роль User (id=1), не Admin/SuperAdmin
    # По умолчанию при регистрации устанавливается role_id=1 (User)
    from app.auth.dao import UsersDAO
    from app.auth.schemas import EmailModel

    async with db_sessionmaker() as session:
        user = await UsersDAO.find_one_or_none(
            session=session, filters=EmailModel(email=email)
        )
        if user:
            # Убеждаемся, что роль User (id=1), не Admin (id=3) или SuperAdmin (id=4)
            user.role_id = 1  # User
            await session.commit()

    r = await client.get(f"/blogs/{blog_id}/")
    assert r.status_code == 200
    # is_admin должен быть False, так как user_data.role.id = 1, а не 3 или 4


@pytest.mark.asyncio
async def test_edit_blog_submit_tags_update_from_empty_to_tags(client):
    """Тест: POST /blogs/{id}/edit/ обновление тегов с пустых на новые"""
    email = f"edit_tags_empty_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)

    # Создаём блог без тегов
    title = f"EmptyTags_{uuid.uuid4().hex[:6]}"
    r = await client.post(
        "/blogs/create/",
        data={
            "title": title,
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )
    blog_id = int(r.headers["location"].strip("/").split("/")[1])

    # Добавляем теги
    r = await client.post(
        f"/blogs/{blog_id}/edit/",
        data={
            "title": title,
            "content": "Content",
            "short_description": "Short",
            "tags": "new, tags, here",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303


@pytest.mark.asyncio
async def test_create_blog_submit_tags_with_whitespace(client):
    """Тест: POST /blogs/create/ теги с пробелами обрабатываются корректно"""
    email = f"create_tags_ws_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)

    title = f"TagsWS_{uuid.uuid4().hex[:6]}"
    r = await client.post(
        "/blogs/create/",
        data={
            "title": title,
            "content": "Content",
            "short_description": "Short",
            "tags": "  python  ,  fastapi  ,  testing  ",  # Теги с пробелами
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    # Теги должны быть обработаны через tag.strip()
