import uuid

import pytest
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError


class _TagAdd(BaseModel):
    name: str


class _TagFilter(BaseModel):
    id: int | None = None
    name: str | None = None


class _TagUpdate(BaseModel):
    name: str


class _TagUpsert(BaseModel):
    id: int | None = None
    name: str | None = None


@pytest.mark.asyncio
async def test_base_dao_add_add_many_rollback_on_flush_error(
    db_sessionmaker, monkeypatch
):
    from app.api.models import Tag
    from app.dao.base import BaseDAO

    class TagDAO(BaseDAO[Tag]):
        model = Tag

    async with db_sessionmaker() as session:
        called = {"rb": 0}

        orig_rb = session.rollback

        async def _rb():
            called["rb"] += 1
            return await orig_rb()

        async def _boom():
            raise SQLAlchemyError("flush failed")

        monkeypatch.setattr(session, "rollback", _rb)
        monkeypatch.setattr(session, "flush", _boom)

        with pytest.raises(SQLAlchemyError):
            await TagDAO.add(
                session=session, values=_TagAdd(name=f"x_{uuid.uuid4().hex[:6]}")
            )
        assert called["rb"] >= 1

    async with db_sessionmaker() as session:
        called = {"rb": 0}
        orig_rb = session.rollback

        async def _rb():
            called["rb"] += 1
            return await orig_rb()

        async def _boom():
            raise SQLAlchemyError("flush failed")

        monkeypatch.setattr(session, "rollback", _rb)
        monkeypatch.setattr(session, "flush", _boom)

        with pytest.raises(SQLAlchemyError):
            await TagDAO.add_many(
                session=session,
                instances=[_TagAdd(name="a"), _TagAdd(name="b")],
            )
        assert called["rb"] >= 1


@pytest.mark.asyncio
async def test_base_dao_update_delete_bulk_update_rollback_on_execute_error(
    db_sessionmaker, monkeypatch
):
    from app.api.models import Tag
    from app.dao.base import BaseDAO

    class TagDAO(BaseDAO[Tag]):
        model = Tag

    async with db_sessionmaker() as session:
        called = {"rb": 0}
        orig_rb = session.rollback

        async def _rb():
            called["rb"] += 1
            return await orig_rb()

        async def _boom(*args, **kwargs):
            raise SQLAlchemyError("execute failed")

        monkeypatch.setattr(session, "rollback", _rb)
        monkeypatch.setattr(session, "execute", _boom)

        with pytest.raises(SQLAlchemyError):
            await TagDAO.update(
                session=session,
                filters=_TagFilter(id=1),
                values=_TagUpdate(name="upd"),
            )
        assert called["rb"] >= 1

    async with db_sessionmaker() as session:
        called = {"rb": 0}
        orig_rb = session.rollback

        async def _rb():
            called["rb"] += 1
            return await orig_rb()

        async def _boom(*args, **kwargs):
            raise SQLAlchemyError("execute failed")

        monkeypatch.setattr(session, "rollback", _rb)
        monkeypatch.setattr(session, "execute", _boom)

        with pytest.raises(SQLAlchemyError):
            await TagDAO.delete(session=session, filters=_TagFilter(id=1))
        assert called["rb"] >= 1

    async with db_sessionmaker() as session:
        called = {"rb": 0}
        orig_rb = session.rollback

        async def _rb():
            called["rb"] += 1
            return await orig_rb()

        async def _boom(*args, **kwargs):
            raise SQLAlchemyError("execute failed")

        monkeypatch.setattr(session, "rollback", _rb)
        monkeypatch.setattr(session, "execute", _boom)

        with pytest.raises(SQLAlchemyError):
            await TagDAO.bulk_update(
                session=session,
                records=[_TagUpsert(id=1, name="x")],
            )
        assert called["rb"] >= 1


@pytest.mark.asyncio
async def test_base_dao_upsert_raises_value_error_when_no_unique_fields_present(
    db_sessionmaker,
):
    from app.api.models import Tag
    from app.dao.base import BaseDAO

    class TagDAO(BaseDAO[Tag]):
        model = Tag

    async with db_sessionmaker() as session:
        with pytest.raises(ValueError):
            await TagDAO.upsert(
                session=session, unique_fields=["name"], values=_TagUpsert()
            )


@pytest.mark.asyncio
async def test_base_dao_upsert_rollbacks_on_sqlalchemy_error(
    db_sessionmaker, monkeypatch
):
    from app.api.models import Tag
    from app.dao.base import BaseDAO

    class TagDAO(BaseDAO[Tag]):
        model = Tag

    async with db_sessionmaker() as session:
        called = {"rb": 0}
        orig_rb = session.rollback

        async def _rb():
            called["rb"] += 1
            return await orig_rb()

        async def _boom():
            raise SQLAlchemyError("flush failed")

        monkeypatch.setattr(session, "rollback", _rb)
        monkeypatch.setattr(session, "flush", _boom)

        with pytest.raises(SQLAlchemyError):
            await TagDAO.upsert(
                session=session,
                unique_fields=["name"],
                values=_TagUpsert(name="u_x"),
            )
        assert called["rb"] >= 1
