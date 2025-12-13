import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from jose import jwt
from starlette.requests import Request


def _make_request_with_cookie(token: str | None) -> Request:
    cookie = f"users_access_token={token}" if token is not None else ""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"cookie", cookie.encode("latin-1"))] if cookie else [],
        "query_string": b"",
        "server": ("test", 80),
        "client": ("test", 12345),
        "scheme": "http",
        "root_path": "",
    }
    return Request(scope)


def _encode(payload: dict) -> str:
    from app.config import settings

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def test_get_token_missing_cookie_raises():
    from app.auth.dependencies import get_token

    req = _make_request_with_cookie(None)
    with pytest.raises(HTTPException) as e:
        get_token(req)
    assert e.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_and_optional_branches(db_sessionmaker, ensure_user):
    from app.auth.dependencies import get_current_user, get_current_user_optional

    u = await ensure_user(
        "dep_user@example.com",
        password="secret123",
        phone="+70000000101",
        first_name="Dep",
        last_name="User",
    )

    # invalid jwt
    async with db_sessionmaker() as session:
        with pytest.raises(HTTPException) as e:
            await get_current_user(token="not-a-jwt", session=session)
        assert e.value.status_code == 401

    # expired token => TokenExpiredException
    expired = _encode({"sub": str(u.id), "exp": int(time.time()) - 10})
    async with db_sessionmaker() as session:
        with pytest.raises(HTTPException) as e:
            await get_current_user(token=expired, session=session)
        assert e.value.status_code == 401

    # missing sub => NoUserIdException
    no_sub = _encode({"exp": int(time.time()) + 60})
    async with db_sessionmaker() as session:
        with pytest.raises(HTTPException) as e:
            await get_current_user(token=no_sub, session=session)
        assert e.value.status_code == 401

    # user not found => 401 "User not found"
    missing_user = _encode({"sub": "999999", "exp": int(time.time()) + 60})
    async with db_sessionmaker() as session:
        with pytest.raises(HTTPException) as e:
            await get_current_user(token=missing_user, session=session)
        assert e.value.status_code == 401
        assert e.value.detail == "User not found"

    # ok
    ok = _encode({"sub": str(u.id), "exp": int(time.time()) + 60})
    async with db_sessionmaker() as session:
        got = await get_current_user(token=ok, session=session)
    assert got.id == u.id

    # optional: no token => None
    async with db_sessionmaker() as session:
        assert await get_current_user_optional(token=None, session=session) is None

    # optional: invalid token => None
    async with db_sessionmaker() as session:
        assert await get_current_user_optional(token="bad", session=session) is None

    # optional: expired => None
    async with db_sessionmaker() as session:
        assert await get_current_user_optional(token=expired, session=session) is None

    # optional: ok => user
    async with db_sessionmaker() as session:
        got = await get_current_user_optional(token=ok, session=session)
    assert got is not None and got.id == u.id


@pytest.mark.asyncio
async def test_get_current_admin_user_and_get_blog_info(monkeypatch):
    from app.auth.dependencies import get_blog_info, get_current_admin_user

    admin = SimpleNamespace(role=SimpleNamespace(id=3))
    assert await get_current_admin_user(admin) is admin

    not_admin = SimpleNamespace(role=SimpleNamespace(id=1))
    with pytest.raises(HTTPException) as e:
        await get_current_admin_user(not_admin)
    assert e.value.status_code == 403

    calls = {}

    async def _fake_get_full_blog_info(*, session, blog_id, author_id, user_role_id):
        calls["blog_id"] = blog_id
        calls["author_id"] = author_id
        calls["user_role_id"] = user_role_id
        # Возвращаем dict, который будет преобразован в BlogNotFind
        return {"message": "Test", "status": "error"}

    from app.api import dao as api_dao
    from app.api.schemas import BlogNotFind

    monkeypatch.setattr(api_dao.BlogDAO, "get_full_blog_info", _fake_get_full_blog_info)

    anon = None
    out = await get_blog_info(blog_id=10, session=None, user_data=anon)
    # get_blog_info преобразует dict в BlogNotFind
    assert isinstance(out, BlogNotFind)
    assert out.message == "Test"
    assert out.status == "error"
    assert calls == {"blog_id": 10, "author_id": None, "user_role_id": None}

    calls.clear()
    user_no_role = SimpleNamespace(id=5, role=None)
    out = await get_blog_info(blog_id=11, session=None, user_data=user_no_role)
    assert isinstance(out, BlogNotFind)
    assert calls == {"blog_id": 11, "author_id": 5, "user_role_id": None}
