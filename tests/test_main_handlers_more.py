import time

import pytest
from jose import jwt
from starlette.exceptions import HTTPException as StarletteHTTPException
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


@pytest.mark.asyncio
async def test_http_exception_handler_non_404_html(app, client):
    """Тест: http_exception_handler для не-404 ошибок -> HTML с деталями"""

    # Создаём тестовый роут, который выбрасывает 400
    async def _bad_request():
        raise StarletteHTTPException(status_code=400, detail="Bad Request")

    if not any(getattr(rt, "path", None) == "/test-400" for rt in app.router.routes):
        app.add_api_route("/test-400", _bad_request, methods=["GET"])

    r = await client.get("/test-400", headers={"accept": "text/html"})
    assert r.status_code == 400
    assert "text/html" in r.headers.get("content-type", "").lower()
    assert "Bad Request" in r.text


@pytest.mark.asyncio
async def test_http_exception_handler_404_html_with_user(
    app, client, ensure_user, monkeypatch
):
    """Тест: http_exception_handler для 404 с авторизованным пользователем"""

    email = f"main_404_{time.time()}@example.com"
    phone = f"+7{int(time.time()) % 10**10:010d}"

    user = await ensure_user(
        email,
        password="secret123",
        phone=phone,
    )

    # Мокаем async_session_maker для получения пользователя

    async def _mock_session_maker():
        from app.auth.dao import UsersDAO
        from app.dao.session_maker import SessionDep

        async with SessionDep() as session:
            return await UsersDAO.find_one_or_none_by_id(
                data_id=user.id, session=session
            )

    # Создаём токен
    token = _encode_token({"sub": str(user.id), "exp": int(time.time()) + 60})

    # Запрос с cookie
    r = await client.get(
        "/non-existent-page",
        headers={"accept": "text/html", "cookie": f"users_access_token={token}"},
    )
    assert r.status_code == 404
    assert "text/html" in r.headers.get("content-type", "").lower()


@pytest.mark.asyncio
async def test_get_current_user_optional_from_request_exception_on_int_conversion(
    db_sessionmaker, monkeypatch
):
    """Тест: _get_current_user_optional_from_request при ошибке преобразования int(user_id)"""
    import app.main as main

    monkeypatch.setattr(main, "async_session_maker", db_sessionmaker)

    # Токен с невалидным sub (не число)
    token = _encode_token({"sub": "not-a-number", "exp": int(time.time()) + 60})
    req = _make_request(headers={"cookie": f"users_access_token={token}"})

    # Должен вернуть None из-за ошибки преобразования int(user_id)
    result = await main._get_current_user_optional_from_request(req)
    assert result is None


@pytest.mark.asyncio
async def test_get_current_user_optional_from_request_exception_on_timestamp_conversion(
    db_sessionmaker, monkeypatch
):
    """Тест: _get_current_user_optional_from_request при ошибке преобразования timestamp"""
    import app.main as main

    monkeypatch.setattr(main, "async_session_maker", db_sessionmaker)

    # Токен с невалидным exp (не число, но присутствует)
    # JWT библиотека может выбросить исключение при декодировании
    # или мы получим None при попытке преобразования
    token = _encode_token({"sub": "1", "exp": "invalid"})
    req = _make_request(headers={"cookie": f"users_access_token={token}"})

    # Должен вернуть None из-за ошибки преобразования timestamp
    result = await main._get_current_user_optional_from_request(req)
    assert result is None
