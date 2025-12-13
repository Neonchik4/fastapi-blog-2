import time

import pytest
from jose import jwt
from pydantic import ValidationError


def test_create_access_token_contains_sub_and_future_exp():
    from app.auth.auth import create_access_token
    from app.config import settings

    token = create_access_token({"sub": "123"})
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    assert payload["sub"] == "123"
    assert int(payload["exp"]) > int(time.time())


@pytest.mark.asyncio
async def test_authenticate_user_returns_none_on_missing_user_and_bad_password(
    monkeypatch,
):
    from app.auth import auth as auth_mod
    from app.auth.auth import authenticate_user

    async def _no_user(*args, **kwargs):
        return None

    monkeypatch.setattr(auth_mod.UsersDAO, "find_one_or_none", _no_user)
    assert (
        await authenticate_user(email="x@example.com", password="pw", session=None)
        is None
    )

    class _User:
        password = "hashed"

    async def _has_user(*args, **kwargs):
        return _User()

    monkeypatch.setattr(auth_mod.UsersDAO, "find_one_or_none", _has_user)
    monkeypatch.setattr(auth_mod, "verify_password", lambda **kw: False)
    assert (
        await authenticate_user(email="x@example.com", password="pw", session=None)
        is None
    )

    monkeypatch.setattr(auth_mod, "verify_password", lambda **kw: True)
    u = await authenticate_user(email="x@example.com", password="pw", session=None)
    assert u is not None


def test_auth_schemas_phone_and_password_validation():
    from app.auth.schemas import PhoneModel, SUserRegister, SUserUpdate

    with pytest.raises(ValidationError):
        PhoneModel(phone_number="7000")

    with pytest.raises(ValidationError):
        PhoneModel(phone_number="+12")

    with pytest.raises(ValidationError):
        SUserRegister(
            email="a@example.com",
            phone_number="+70000000000",
            first_name="Abc",
            last_name="Def",
            password="secret123",
            confirm_password="different",
        )

    ok = SUserRegister(
        email="b@example.com",
        phone_number="+70000000001",
        first_name="Abc",
        last_name="Def",
        password="secret123",
        confirm_password="secret123",
    )
    assert ok.password != "secret123"

    with pytest.raises(ValidationError):
        SUserUpdate(password="secret123", confirm_password="x")

    upd = SUserUpdate(password="secret123", confirm_password="secret123")
    assert upd.password != "secret123"
