import json
import uuid
from pathlib import Path

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


@pytest.fixture
def likes_json_file():
    p = Path("data/likes.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    old = p.read_text(encoding="utf-8") if p.exists() else None
    try:
        yield p
    finally:
        if old is None:
            if p.exists():
                p.unlink()
        else:
            p.write_text(old, encoding="utf-8")


@pytest.mark.asyncio
async def test_home_page_basic(client):
    r = await client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "").lower()


@pytest.mark.asyncio
async def test_create_blog_page_requires_auth(client):
    r = await client.get("/blogs/create/", follow_redirects=False)
    assert r.status_code in (401, 302, 303)


@pytest.mark.asyncio
async def test_create_blog_page_renders(client):
    email = f"create_page_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    r = await client.get("/blogs/create/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "").lower()


@pytest.mark.asyncio
async def test_create_blog_submit_validation_error(client, monkeypatch):
    from pydantic import ValidationError

    from app.api.schemas import BlogCreateSchemaBase
    from app.pages import views

    email = f"create_val_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    original_init = BlogCreateSchemaBase.__init__

    def mock_init(self, *args, **kwargs):
        try:
            original_init(self, title=None, content="", short_description="", tags=[])
        except ValidationError:
            raise

    monkeypatch.setattr(BlogCreateSchemaBase, "__init__", mock_init)
    monkeypatch.setattr(views, "BlogCreateSchemaBase", BlogCreateSchemaBase)
    r = await client.post(
        "/blogs/create/",
        data={
            "title": "Test",
            "content": "Content",
            "short_description": "Short",
        },
    )
    assert r.status_code == 400
    assert "Ошибка валидации" in r.text


@pytest.mark.asyncio
async def test_create_blog_submit_integrity_error(client):
    email = f"create_int_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    title = f"Unique_{uuid.uuid4().hex[:6]}"
    await client.post(
        "/blogs/create/",
        data={
            "title": title,
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )
    r = await client.post(
        "/blogs/create/",
        data={
            "title": title,
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
    )
    assert r.status_code == 400
    assert "Блог с таким заголовком уже существует" in r.text


@pytest.mark.asyncio
async def test_create_blog_submit_without_tags(client):
    email = f"create_notags_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    r = await client.post(
        "/blogs/create/",
        data={
            "title": f"NoTags_{uuid.uuid4().hex[:6]}",
            "content": "Content",
            "short_description": "Short",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303


@pytest.mark.asyncio
async def test_edit_blog_page_not_found(client):
    email = f"edit_404_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    r = await client.get("/blogs/999999/edit/")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_edit_blog_page_permission_denied(client):
    email1 = f"author1_{uuid.uuid4().hex[:8]}@example.com"
    phone1 = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email1, phone=phone1)
    r = await client.post(
        "/blogs/create/",
        data={
            "title": f"Blog_{uuid.uuid4().hex[:6]}",
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )
    blog_id = int(r.headers["location"].strip("/").split("/")[1])
    email2 = f"author2_{uuid.uuid4().hex[:8]}@example.com"
    phone2 = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email2, phone=phone2)
    r = await client.get(f"/blogs/{blog_id}/edit/")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_edit_blog_page_with_tags(client):
    email = f"edit_tags_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    r = await client.post(
        "/blogs/create/",
        data={
            "title": f"Tags_{uuid.uuid4().hex[:6]}",
            "content": "Content",
            "short_description": "Short",
            "tags": "python, fastapi",
        },
        follow_redirects=False,
    )
    blog_id = int(r.headers["location"].strip("/").split("/")[1])
    r = await client.get(f"/blogs/{blog_id}/edit/")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_edit_blog_page_without_tags(client):
    email = f"edit_notags_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    r = await client.post(
        "/blogs/create/",
        data={
            "title": f"NoTags_{uuid.uuid4().hex[:6]}",
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )
    blog_id = int(r.headers["location"].strip("/").split("/")[1])
    r = await client.get(f"/blogs/{blog_id}/edit/")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_edit_blog_page_user_role_none(app, client):
    email = f"edit_norole_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    r = await client.post(
        "/blogs/create/",
        data={
            "title": f"Blog_{uuid.uuid4().hex[:6]}",
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )
    blog_id = int(r.headers["location"].strip("/").split("/")[1])
    from types import SimpleNamespace

    from app.auth.dependencies import get_current_user

    async def _mock_get_current_user():
        user_obj = SimpleNamespace()
        user_obj.id = 1
        user_obj.role = None
        return user_obj

    app.dependency_overrides[get_current_user] = _mock_get_current_user
    try:
        r = await client.get(f"/blogs/{blog_id}/edit/")
        assert r.status_code == 200
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_edit_blog_submit_validation_error_blog_not_found(client):
    email = f"edit_val404_{uuid.uuid4().hex[:8]}@example.com"
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
async def test_edit_blog_submit_validation_error_with_blog(client, monkeypatch):
    from pydantic import ValidationError

    from app.api.schemas import BlogCreateSchemaBase
    from app.pages import views

    email = f"edit_val_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    r = await client.post(
        "/blogs/create/",
        data={
            "title": f"Blog_{uuid.uuid4().hex[:6]}",
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )
    blog_id = int(r.headers["location"].strip("/").split("/")[1])
    original_init = BlogCreateSchemaBase.__init__

    def mock_init(self, *args, **kwargs):
        try:
            original_init(self, title=None, content="", short_description="", tags=[])
        except ValidationError:
            raise

    monkeypatch.setattr(BlogCreateSchemaBase, "__init__", mock_init)
    monkeypatch.setattr(views, "BlogCreateSchemaBase", BlogCreateSchemaBase)
    r = await client.post(
        f"/blogs/{blog_id}/edit/",
        data={
            "title": "Test",
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
    )
    assert r.status_code == 400
    assert "Ошибка валидации" in r.text


@pytest.mark.asyncio
async def test_edit_blog_submit_tags_clear(client):
    email = f"edit_clear_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    r = await client.post(
        "/blogs/create/",
        data={
            "title": f"Blog_{uuid.uuid4().hex[:6]}",
            "content": "Content",
            "short_description": "Short",
            "tags": "python, fastapi",
        },
        follow_redirects=False,
    )
    blog_id = int(r.headers["location"].strip("/").split("/")[1])
    r = await client.post(
        f"/blogs/{blog_id}/edit/",
        data={
            "title": f"Blog_{uuid.uuid4().hex[:6]}",
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303


@pytest.mark.asyncio
async def test_edit_blog_submit_integrity_error_blog_not_found_after_rollback(
    client, db_sessionmaker
):
    email = f"edit_int404_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    title1 = f"Title1_{uuid.uuid4().hex[:6]}"
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
    title2 = f"Title2_{uuid.uuid4().hex[:6]}"
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
    from app.api.dao import BlogDAO

    async with db_sessionmaker() as session:
        blog = await BlogDAO.find_one_or_none_by_id(session=session, data_id=blog_id2)
        if blog:
            await session.delete(blog)
            await session.commit()
    r = await client.post(
        f"/blogs/{blog_id2}/edit/",
        data={
            "title": title1,
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
    )
    assert r.status_code in (400, 404)


@pytest.mark.asyncio
async def test_blogs_page_author_found(client, ensure_user):
    email = f"author_found_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    user = await ensure_user(
        email, password="secret123", phone=phone, first_name="Author", last_name="Found"
    )
    r = await client.get("/blogs/", params={"author_id": user.id})
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "").lower()


@pytest.mark.asyncio
async def test_blogs_page_tag_found(client):
    email = f"tag_found_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    tag_name = f"tag_{uuid.uuid4().hex[:6]}"
    r = await client.post(
        "/blogs/create/",
        data={
            "title": f"TagBlog_{uuid.uuid4().hex[:6]}",
            "content": "Content",
            "short_description": "Short",
            "tags": tag_name,
        },
        follow_redirects=False,
    )
    r = await client.get("/blogs/", params={"tag": tag_name})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_blogs_page_search_found(client):
    email = f"search_found_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    search_term = f"UniqueSearch_{uuid.uuid4().hex[:6]}"
    r = await client.post(
        "/blogs/create/",
        data={
            "title": search_term,
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )
    r = await client.get("/blogs/", params={"search": search_term})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_liked_blogs_page_redirect_anon(client):
    r = await client.get("/blogs/liked/", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/auth/?mode=login"


@pytest.mark.asyncio
async def test_liked_blogs_page_with_likes(client, likes_json_file):
    email = f"liked_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    me = (await client.get("/auth/me/")).json()
    user_id = me["id"]
    r = await client.post(
        "/blogs/create/",
        data={
            "title": f"Liked_{uuid.uuid4().hex[:6]}",
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )
    blog_id = int(r.headers["location"].strip("/").split("/")[1])
    likes_json_file.write_text(
        json.dumps([{"user_id": user_id, "post_id": blog_id, "liked": True}]),
        encoding="utf-8",
    )
    r = await client.get("/blogs/liked/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "").lower()


@pytest.mark.asyncio
async def test_liked_blogs_page_no_likes(client, likes_json_file):
    email = f"no_likes_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    likes_json_file.write_text("[]", encoding="utf-8")
    r = await client.get("/blogs/liked/")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_liked_blogs_page_invalid_json(client, likes_json_file):
    email = f"invalid_json_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    likes_json_file.write_text("{ invalid", encoding="utf-8")
    r = await client.get("/blogs/liked/")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_liked_blogs_page_file_not_exists(client):
    email = f"no_file_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    p = Path("data/likes.json")
    if p.exists():
        p.unlink()
    try:
        r = await client.get("/blogs/liked/")
        assert r.status_code == 200
    finally:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("[]", encoding="utf-8")


@pytest.mark.asyncio
async def test_liked_blogs_page_liked_false_filtered(client, likes_json_file):
    email = f"liked_false_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    me = (await client.get("/auth/me/")).json()
    user_id = me["id"]
    r = await client.post(
        "/blogs/create/",
        data={
            "title": f"Blog_{uuid.uuid4().hex[:6]}",
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )
    blog_id = int(r.headers["location"].strip("/").split("/")[1])
    likes_json_file.write_text(
        json.dumps([{"user_id": user_id, "post_id": blog_id, "liked": False}]),
        encoding="utf-8",
    )
    r = await client.get("/blogs/liked/")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_drafts_page(client):
    email = f"drafts_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    await client.post(
        "/api/add_post/",
        json={
            "title": f"Draft_{uuid.uuid4().hex[:6]}",
            "content": "Content",
            "short_description": "Short",
            "tags": [],
        },
    )
    r = await client.get("/blogs/drafts/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "").lower()


@pytest.mark.asyncio
async def test_all_drafts_page_admin(client, ensure_user, set_user_role):
    email = f"all_drafts_admin_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    user = await ensure_user(email, password="secret123", phone=phone)
    await set_user_role(user.id, 3)
    r = await client.get("/blogs/all-drafts/")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_all_drafts_page_superadmin(client, ensure_user, set_user_role):
    email = f"all_drafts_super_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    user = await ensure_user(email, password="secret123", phone=phone)
    await set_user_role(user.id, 4)
    r = await client.get("/blogs/all-drafts/")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_all_drafts_page_user_no_role(client):
    email = f"all_drafts_user_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    r = await client.get("/blogs/all-drafts/")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_blog_details_with_user(client):
    email = f"details_user_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    r = await client.post(
        "/blogs/create/",
        data={
            "title": f"Details_{uuid.uuid4().hex[:6]}",
            "content": "Content **bold**",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )
    blog_id = int(r.headers["location"].strip("/").split("/")[1])
    r = await client.get(f"/blogs/{blog_id}/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "").lower()
    assert "<strong>bold</strong>" in r.text


@pytest.mark.asyncio
async def test_blog_details_without_user(client):
    email = f"details_anon_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    r = await client.post(
        "/blogs/create/",
        data={
            "title": f"AnonDetails_{uuid.uuid4().hex[:6]}",
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )
    blog_id = int(r.headers["location"].strip("/").split("/")[1])
    client.cookies.clear()
    r = await client.get(f"/blogs/{blog_id}/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "").lower()


@pytest.mark.asyncio
async def test_blog_details_user_role_none(client):
    email = f"details_norole_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    r = await client.post(
        "/blogs/create/",
        data={
            "title": f"NoRoleDetails_{uuid.uuid4().hex[:6]}",
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )
    blog_id = int(r.headers["location"].strip("/").split("/")[1])
    r = await client.get(f"/blogs/{blog_id}/")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_auth_page_with_message(client):
    r = await client.get("/auth/?mode=register&message=Test%20message")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "").lower()


@pytest.mark.asyncio
async def test_auth_page_with_user(client):
    email = f"auth_user_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    r = await client.get("/auth/")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_register_user_view_validation_error_html(client):
    r = await client.post(
        "/auth/register/form",
        data={"email": "bad@example.com"},
    )
    assert r.status_code == 400
    assert "text/html" in r.headers.get("content-type", "").lower()


@pytest.mark.asyncio
async def test_register_user_view_duplicate_email_html(client):
    email = f"dup_email_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await client.post(
        "/auth/register/form",
        data={
            "email": email,
            "phone_number": phone,
            "first_name": "Test",
            "last_name": "User",
            "password": "secret123",
            "confirm_password": "secret123",
        },
        headers={"x-requested-with": "XMLHttpRequest"},
    )
    r = await client.post(
        "/auth/register/form",
        data={
            "email": email,
            "phone_number": f"+7{uuid.uuid4().int % 10**10:010d}",
            "first_name": "Test",
            "last_name": "User",
            "password": "secret123",
            "confirm_password": "secret123",
        },
    )
    assert r.status_code == 400
    assert "email" in r.text.lower()


@pytest.mark.asyncio
async def test_register_user_view_duplicate_phone_html(client):
    email1 = f"dup_phone1_{uuid.uuid4().hex[:8]}@example.com"
    email2 = f"dup_phone2_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await client.post(
        "/auth/register/form",
        data={
            "email": email1,
            "phone_number": phone,
            "first_name": "Test",
            "last_name": "User",
            "password": "secret123",
            "confirm_password": "secret123",
        },
        headers={"x-requested-with": "XMLHttpRequest"},
    )
    r = await client.post(
        "/auth/register/form",
        data={
            "email": email2,
            "phone_number": phone,
            "first_name": "Test",
            "last_name": "User",
            "password": "secret123",
            "confirm_password": "secret123",
        },
    )
    assert r.status_code == 400
    assert "телефон" in r.text.lower() or "phone" in r.text.lower()


@pytest.mark.asyncio
async def test_register_user_view_integrity_error_html(client):
    email = f"int_error_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await client.post(
        "/auth/register/form",
        data={
            "email": email,
            "phone_number": phone,
            "first_name": "Test",
            "last_name": "User",
            "password": "secret123",
            "confirm_password": "secret123",
        },
        headers={"x-requested-with": "XMLHttpRequest"},
    )
    r = await client.post(
        "/auth/register/form",
        data={
            "email": email,
            "phone_number": phone,
            "first_name": "Test",
            "last_name": "User",
            "password": "secret123",
            "confirm_password": "secret123",
        },
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_register_user_view_success_redirect(client):
    email = f"success_red_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    r = await client.post(
        "/auth/register/form",
        data={
            "email": email,
            "phone_number": phone,
            "first_name": "Test",
            "last_name": "User",
            "password": "secret123",
            "confirm_password": "secret123",
        },
        follow_redirects=False,
    )
    assert r.status_code in (201, 303)


@pytest.mark.asyncio
async def test_login_user_view_success_html(client):
    email = f"login_html_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await client.post(
        "/auth/register/",
        json={
            "email": email,
            "phone_number": phone,
            "first_name": "Test",
            "last_name": "User",
            "password": "secret123",
            "confirm_password": "secret123",
        },
    )
    r = await client.post(
        "/auth/login/form",
        data={"email": email, "password": "secret123"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    assert "users_access_token" in r.cookies


@pytest.mark.asyncio
async def test_login_user_view_exception_html(client, monkeypatch):
    email = f"login_exc_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await client.post(
        "/auth/register/",
        json={
            "email": email,
            "phone_number": phone,
            "first_name": "Test",
            "last_name": "User",
            "password": "secret123",
            "confirm_password": "secret123",
        },
    )
    from app.pages import views

    async def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(views, "authenticate_user", _boom)
    r = await client.post(
        "/auth/login/form",
        data={"email": email, "password": "secret123"},
    )
    assert r.status_code == 503
    assert "Сервис недоступен" in r.text


@pytest.mark.asyncio
async def test_profile_update_validation_error(client):
    email = f"profile_val_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    r = await client.post(
        "/profile/",
        data={"phone_number": "invalid"},
    )
    assert r.status_code == 400
    assert "Ошибка валидации" in r.text


@pytest.mark.asyncio
async def test_profile_update_no_changes(client):
    email = f"profile_noch_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    r = await client.post("/profile/", data={})
    assert r.status_code == 200
    assert "Нет изменений для сохранения" in r.text


@pytest.mark.asyncio
async def test_profile_update_duplicate_phone(client):
    email1 = f"profile_ph1_{uuid.uuid4().hex[:8]}@example.com"
    email2 = f"profile_ph2_{uuid.uuid4().hex[:8]}@example.com"
    phone1 = f"+7{uuid.uuid4().int % 10**10:010d}"
    phone2 = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email1, phone=phone1)
    await client.post(
        "/auth/register/",
        json={
            "email": email2,
            "phone_number": phone2,
            "first_name": "Test",
            "last_name": "User",
            "password": "secret123",
            "confirm_password": "secret123",
        },
    )
    await client.post("/auth/login/", json={"email": email1, "password": "secret123"})
    r = await client.post(
        "/profile/",
        data={"phone_number": phone2},
    )
    assert r.status_code == 400
    assert "телефон" in r.text.lower() or "phone" in r.text.lower()


@pytest.mark.asyncio
async def test_profile_update_user_not_found(client, db_sessionmaker):
    email = f"profile_404_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    from app.auth.dao import UsersDAO
    from app.auth.schemas import EmailModel

    async with db_sessionmaker() as session:
        user = await UsersDAO.find_one_or_none(
            session=session, filters=EmailModel(email=email)
        )
        if user:
            await session.delete(user)
            await session.commit()
    r = await client.post(
        "/profile/",
        data={"first_name": "NewName"},
    )
    assert r.status_code in (401, 404)


@pytest.mark.asyncio
async def test_profile_update_success_with_role_id(client):
    email = f"profile_role_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    r = await client.post(
        "/profile/",
        data={
            "first_name": "Updated",
            "role_id": "2",
        },
    )
    assert r.status_code == 200
    assert "Профиль успешно обновлен" in r.text or "обновлен" in r.text.lower()


@pytest.mark.asyncio
async def test_profile_update_non_string_values(client):
    email = f"profile_nonstr_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    r = await client.post(
        "/profile/",
        data={
            "first_name": "Test",
        },
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_edit_blog_submit_admin_with_role_id_3(
    client, ensure_user, set_user_role
):
    email1 = f"author_admin3_{uuid.uuid4().hex[:8]}@example.com"
    phone1 = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email1, phone=phone1)
    r = await client.post(
        "/blogs/create/",
        data={
            "title": f"Blog_{uuid.uuid4().hex[:6]}",
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )
    blog_id = int(r.headers["location"].strip("/").split("/")[1])
    email2 = f"admin3_{uuid.uuid4().hex[:8]}@example.com"
    phone2 = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email2, phone=phone2)
    user = await ensure_user(email2, password="secret123", phone=phone2)
    await set_user_role(user.id, 3)
    r = await client.post(
        f"/blogs/{blog_id}/edit/",
        data={
            "title": f"Blog_{uuid.uuid4().hex[:6]}",
            "content": "Admin content",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303


@pytest.mark.asyncio
async def test_edit_blog_submit_admin_with_role_id_4(
    client, ensure_user, set_user_role
):
    email1 = f"author_admin4_{uuid.uuid4().hex[:8]}@example.com"
    phone1 = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email1, phone=phone1)
    r = await client.post(
        "/blogs/create/",
        data={
            "title": f"Blog_{uuid.uuid4().hex[:6]}",
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )
    blog_id = int(r.headers["location"].strip("/").split("/")[1])
    email2 = f"admin4_{uuid.uuid4().hex[:8]}@example.com"
    phone2 = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email2, phone=phone2)
    user = await ensure_user(email2, password="secret123", phone=phone2)
    await set_user_role(user.id, 4)
    r = await client.post(
        f"/blogs/{blog_id}/edit/",
        data={
            "title": f"Blog_{uuid.uuid4().hex[:6]}",
            "content": "SuperAdmin content",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303


@pytest.mark.asyncio
async def test_edit_blog_page_admin_with_role_id_3(client, ensure_user, set_user_role):
    email1 = f"author_edit3_{uuid.uuid4().hex[:8]}@example.com"
    phone1 = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email1, phone=phone1)
    r = await client.post(
        "/blogs/create/",
        data={
            "title": f"Blog_{uuid.uuid4().hex[:6]}",
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )
    blog_id = int(r.headers["location"].strip("/").split("/")[1])
    email2 = f"edit3_{uuid.uuid4().hex[:8]}@example.com"
    phone2 = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email2, phone=phone2)
    user = await ensure_user(email2, password="secret123", phone=phone2)
    await set_user_role(user.id, 3)
    r = await client.get(f"/blogs/{blog_id}/edit/")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_edit_blog_page_admin_with_role_id_4(client, ensure_user, set_user_role):
    email1 = f"author_edit4_{uuid.uuid4().hex[:8]}@example.com"
    phone1 = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email1, phone=phone1)
    r = await client.post(
        "/blogs/create/",
        data={
            "title": f"Blog_{uuid.uuid4().hex[:6]}",
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )
    blog_id = int(r.headers["location"].strip("/").split("/")[1])
    email2 = f"edit4_{uuid.uuid4().hex[:8]}@example.com"
    phone2 = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email2, phone=phone2)
    user = await ensure_user(email2, password="secret123", phone=phone2)
    await set_user_role(user.id, 4)
    r = await client.get(f"/blogs/{blog_id}/edit/")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_blog_details_admin_role_id_3(client, ensure_user, set_user_role):
    email = f"details_admin3_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    r = await client.post(
        "/blogs/create/",
        data={
            "title": f"Blog_{uuid.uuid4().hex[:6]}",
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )
    blog_id = int(r.headers["location"].strip("/").split("/")[1])
    user = await ensure_user(email, password="secret123", phone=phone)
    await set_user_role(user.id, 3)
    r = await client.get(f"/blogs/{blog_id}/")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_blog_details_admin_role_id_4(client, ensure_user, set_user_role):
    email = f"details_admin4_{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+7{uuid.uuid4().int % 10**10:010d}"
    await _register_and_login(client, email=email, phone=phone)
    r = await client.post(
        "/blogs/create/",
        data={
            "title": f"Blog_{uuid.uuid4().hex[:6]}",
            "content": "Content",
            "short_description": "Short",
            "tags": "",
        },
        follow_redirects=False,
    )
    blog_id = int(r.headers["location"].strip("/").split("/")[1])
    user = await ensure_user(email, password="secret123", phone=phone)
    await set_user_role(user.id, 4)
    r = await client.get(f"/blogs/{blog_id}/")
    assert r.status_code == 200
