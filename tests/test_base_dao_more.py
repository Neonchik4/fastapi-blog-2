import pytest
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError


class _TagAdd(BaseModel):
    name: str


class _TagFilter(BaseModel):
    id: int | None = None
    name: str | None = None


@pytest.mark.asyncio
async def test_base_dao_find_one_or_none_by_id_sqlalchemy_error(
    db_sessionmaker, monkeypatch
):
    """Тест: find_one_or_none_by_id при SQLAlchemyError -> пробрасывает исключение"""
    from app.api.models import Tag
    from app.dao.base import BaseDAO

    class TagDAO(BaseDAO[Tag]):
        model = Tag

    async with db_sessionmaker() as session:

        async def _boom(*args, **kwargs):
            raise SQLAlchemyError("db error")

        monkeypatch.setattr(session, "execute", _boom)

        with pytest.raises(SQLAlchemyError):
            await TagDAO.find_one_or_none_by_id(data_id=1, session=session)


@pytest.mark.asyncio
async def test_base_dao_find_one_or_none_sqlalchemy_error(db_sessionmaker, monkeypatch):
    """Тест: find_one_or_none при SQLAlchemyError -> пробрасывает исключение"""
    from app.api.models import Tag
    from app.dao.base import BaseDAO

    class TagDAO(BaseDAO[Tag]):
        model = Tag

    async with db_sessionmaker() as session:

        async def _boom(*args, **kwargs):
            raise SQLAlchemyError("db error")

        monkeypatch.setattr(session, "execute", _boom)

        with pytest.raises(SQLAlchemyError):
            await TagDAO.find_one_or_none(session=session, filters=_TagFilter(name="x"))


@pytest.mark.asyncio
async def test_base_dao_find_all_sqlalchemy_error(db_sessionmaker, monkeypatch):
    """Тест: find_all при SQLAlchemyError -> пробрасывает исключение"""
    from app.api.models import Tag
    from app.dao.base import BaseDAO

    class TagDAO(BaseDAO[Tag]):
        model = Tag

    async with db_sessionmaker() as session:

        async def _boom(*args, **kwargs):
            raise SQLAlchemyError("db error")

        monkeypatch.setattr(session, "execute", _boom)

        with pytest.raises(SQLAlchemyError):
            await TagDAO.find_all(session=session, filters=None)


@pytest.mark.asyncio
async def test_base_dao_count_sqlalchemy_error(db_sessionmaker, monkeypatch):
    """Тест: count при SQLAlchemyError -> пробрасывает исключение"""
    from app.api.models import Tag
    from app.dao.base import BaseDAO

    class TagDAO(BaseDAO[Tag]):
        model = Tag

    async with db_sessionmaker() as session:

        async def _boom(*args, **kwargs):
            raise SQLAlchemyError("db error")

        monkeypatch.setattr(session, "execute", _boom)

        with pytest.raises(SQLAlchemyError):
            await TagDAO.count(session=session, filters=_TagFilter(name="x"))


@pytest.mark.asyncio
async def test_base_dao_paginate_sqlalchemy_error(db_sessionmaker, monkeypatch):
    """Тест: paginate при SQLAlchemyError -> пробрасывает исключение"""
    from app.api.models import Tag
    from app.dao.base import BaseDAO

    class TagDAO(BaseDAO[Tag]):
        model = Tag

    async with db_sessionmaker() as session:

        async def _boom(*args, **kwargs):
            raise SQLAlchemyError("db error")

        monkeypatch.setattr(session, "execute", _boom)

        with pytest.raises(SQLAlchemyError):
            await TagDAO.paginate(session=session, page=1, page_size=10, filters=None)


@pytest.mark.asyncio
async def test_base_dao_find_by_ids_sqlalchemy_error(db_sessionmaker, monkeypatch):
    """Тест: find_by_ids при SQLAlchemyError -> пробрасывает исключение"""
    from app.api.models import Tag
    from app.dao.base import BaseDAO

    class TagDAO(BaseDAO[Tag]):
        model = Tag

    async with db_sessionmaker() as session:

        async def _boom(*args, **kwargs):
            raise SQLAlchemyError("db error")

        monkeypatch.setattr(session, "execute", _boom)

        with pytest.raises(SQLAlchemyError):
            await TagDAO.find_by_ids(session=session, ids=[1, 2, 3])


@pytest.mark.asyncio
async def test_base_dao_delete_sqlalchemy_error(db_sessionmaker, monkeypatch):
    """Тест: delete при SQLAlchemyError -> rollback и пробрасывает исключение"""
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
            await TagDAO.delete(session=session, filters=_TagFilter(id=1))
        assert called["rb"] >= 1
