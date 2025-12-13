from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_get_blogs_returns_500_on_unhandled_exception(client, monkeypatch):
    from app.api import dao as api_dao

    async def _boom(*args, **kwargs):
        raise RuntimeError("dao down")

    monkeypatch.setattr(api_dao.BlogDAO, "get_blog_list", _boom)
    r = await client.get(
        "/api/blogs/",
        params={"page": 1, "page_size": 10},
        headers={"accept": "application/json"},
    )
    assert r.status_code == 500
    assert r.json() == {"detail": "Ошибка сервера"}


@pytest.mark.asyncio
async def test_add_post_without_tags_field_is_ok(client):
    await client.post(
        "/auth/register/",
        json={
            "email": "api_router_no_tags@example.com",
            "phone_number": "+70000000331",
            "first_name": "Api",
            "last_name": "NoTags",
            "password": "secret123",
            "confirm_password": "secret123",
        },
    )
    r = await client.post(
        "/auth/login/",
        json={"email": "api_router_no_tags@example.com", "password": "secret123"},
    )
    assert r.status_code == 200

    r = await client.post(
        "/api/add_post/",
        json={
            "title": "NoTagsTitle",
            "content": "Hello",
            "short_description": "Short",
            "tags": [],
        },
    )
    assert r.status_code == 200
    assert r.json()["status"] == "success"


@pytest.mark.asyncio
async def test_delete_and_change_blog_status_user_role_none_path(
    app, client, monkeypatch
):
    from app.api import dao as api_dao
    from app.auth.dependencies import get_current_user

    async def _fake_current_user():
        return SimpleNamespace(id=123, role=None)

    app.dependency_overrides[get_current_user] = _fake_current_user
    try:

        async def _ok_delete(session, blog_id, user_id, user_role_id):
            assert user_role_id is None
            return {"status": "success", "blog_id": blog_id}

        async def _ok_change(session, blog_id, new_status, user_id, user_role_id):
            assert user_role_id is None
            return {"status": "success", "blog_id": blog_id, "new_status": new_status}

        monkeypatch.setattr(api_dao.BlogDAO, "delete_blog", _ok_delete)
        monkeypatch.setattr(api_dao.BlogDAO, "change_blog_status", _ok_change)

        r = await client.patch(
            "/api/change_blog_status/10", params={"new_status": "draft"}
        )
        assert r.status_code == 200
        assert r.json()["status"] == "success"

        r = await client.delete("/api/delete_blog/10")
        assert r.status_code == 200
        assert r.json()["status"] == "success"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
