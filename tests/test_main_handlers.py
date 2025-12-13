import time

import pytest
from jose import jwt
from starlette.requests import Request


def _make_request(*, path: str = "/", headers: dict[str, str] | None = None) -> Request:
    hdrs = []
    for k, v in (headers or {}).items():
        hdrs.append((k.lower().encode("latin-1"), v.encode("latin-1")))
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": hdrs,
        "query_string": b"",
        "server": ("test", 80),
        "client": ("test", 12345),
        "scheme": "http",
        "root_path": "",
    }
    return Request(scope)


def _encode_token(payload: dict) -> str:
    from app.config import settings

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def test_is_api_like_path_and_wants_html_unit():
    import app.main as main

    assert main._is_api_like_path("/api/x") is True
    assert main._is_api_like_path("/docs") is True
    assert main._is_api_like_path("/openapi.json") is True
    assert main._is_api_like_path("/auth/") is False
    assert main._is_api_like_path("/auth/login") is True

    r = _make_request(headers={"accept": "text/html"})
    assert main._wants_html(r) is True

    r = _make_request(headers={"accept": "application/json"})
    assert main._wants_html(r) is False

    r = _make_request(headers={"content-type": "application/json"})
    assert main._wants_html(r) is False

    r = _make_request(headers={"accept": "*/*"})
    assert main._wants_html(r) is True

    r = _make_request(headers={})
    assert main._wants_html(r) is True


@pytest.mark.asyncio
async def test_get_current_user_optional_from_request_branches(
    db_sessionmaker, ensure_user, monkeypatch
):
    import app.main as main
    from app.auth.dao import UsersDAO

    # важно: используем тестовую БД, а не "боевую" async_session_maker из app.dao.database
    monkeypatch.setattr(main, "async_session_maker", db_sessionmaker)

    # no cookie
    req = _make_request()
    assert await main._get_current_user_optional_from_request(req) is None

    # invalid jwt
    req = _make_request(headers={"cookie": "users_access_token=not-a-jwt"})
    assert await main._get_current_user_optional_from_request(req) is None

    # missing exp
    token = _encode_token({"sub": "1"})
    req = _make_request(headers={"cookie": f"users_access_token={token}"})
    assert await main._get_current_user_optional_from_request(req) is None

    # non-int exp
    token = _encode_token({"sub": "1", "exp": "nope"})
    req = _make_request(headers={"cookie": f"users_access_token={token}"})
    assert await main._get_current_user_optional_from_request(req) is None

    # expired exp
    token = _encode_token({"sub": "1", "exp": int(time.time()) - 5})
    req = _make_request(headers={"cookie": f"users_access_token={token}"})
    assert await main._get_current_user_optional_from_request(req) is None

    # missing sub
    token = _encode_token({"exp": int(time.time()) + 60})
    req = _make_request(headers={"cookie": f"users_access_token={token}"})
    assert await main._get_current_user_optional_from_request(req) is None

    # user exists
    u = await ensure_user(
        "main_user@example.com",
        password="secret123",
        phone="+70000000001",
        first_name="Main",
        last_name="User",
    )
    token = _encode_token({"sub": str(u.id), "exp": int(time.time()) + 60})
    req = _make_request(headers={"cookie": f"users_access_token={token}"})
    got = await main._get_current_user_optional_from_request(req)
    assert got is not None and got.id == u.id

    # UsersDAO fails => function must swallow and return None
    async def _boom(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(UsersDAO, "find_one_or_none_by_id", _boom)
    token = _encode_token({"sub": str(u.id), "exp": int(time.time()) + 60})
    req = _make_request(headers={"cookie": f"users_access_token={token}"})
    assert await main._get_current_user_optional_from_request(req) is None
