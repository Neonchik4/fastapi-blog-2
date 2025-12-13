import uuid

import pytest
from pydantic import BaseModel


class _TagAdd(BaseModel):
    name: str


class _TagFilter(BaseModel):
    id: int | None = None
    name: str | None = None


class _TagUpdate(BaseModel):
    name: str


class _TagBulk(BaseModel):
    id: int | None = None
    name: str | None = None


class _EmptyFilters(BaseModel):
    pass


@pytest.mark.asyncio
async def test_base_dao_crud_find_count_paginate_upsert_bulk_update(db_sessionmaker):
    """Функции: BaseDAO.* (на примере модели Tag)"""
    from app.api.models import Tag
    from app.dao.base import BaseDAO

    class TagDAO(BaseDAO[Tag]):
        model = Tag

    async with db_sessionmaker() as session:
        t1 = await TagDAO.add(
            session=session, values=_TagAdd(name=f"t_{uuid.uuid4().hex[:6]}")
        )
        await session.commit()

    async with db_sessionmaker() as session:
        got = await TagDAO.find_one_or_none_by_id(data_id=t1.id, session=session)
        assert got is not None and got.id == t1.id

        missing = await TagDAO.find_one_or_none_by_id(data_id=999999, session=session)
        assert missing is None

        by_name = await TagDAO.find_one_or_none(
            session=session, filters=_TagFilter(name=t1.name)
        )
        assert by_name is not None and by_name.id == t1.id
        all_tags = await TagDAO.find_all(session=session, filters=None)
        assert any(t.id == t1.id for t in all_tags)

        new_tags = await TagDAO.add_many(
            session=session,
            instances=[
                _TagAdd(name=f"a_{uuid.uuid4().hex[:6]}"),
                _TagAdd(name=f"b_{uuid.uuid4().hex[:6]}"),
            ],
        )
        assert len(new_tags) == 2
        await session.commit()

    async with db_sessionmaker() as session:
        c = await TagDAO.count(session=session, filters=_TagFilter(name=t1.name))
        assert c == 1

        page1 = await TagDAO.paginate(
            session=session, page=1, page_size=2, filters=None
        )
        assert len(page1) <= 2

        updated = await TagDAO.update(
            session=session,
            filters=_TagFilter(id=t1.id),
            values=_TagUpdate(name=f"upd_{uuid.uuid4().hex[:6]}"),
        )
        assert updated == 1
        await session.commit()

    async with db_sessionmaker() as session:
        ids = [t1.id]
        found = await TagDAO.find_by_ids(session=session, ids=ids)
        assert len(found) == 1 and found[0].id == t1.id

        created = await TagDAO.upsert(
            session=session,
            unique_fields=["name"],
            values=_TagBulk(name=f"u_{uuid.uuid4().hex[:6]}"),
        )
        created_id = created.id
        updated_obj = await TagDAO.upsert(
            session=session,
            unique_fields=["name"],
            values=_TagBulk(id=created_id, name=created.name),
        )
        assert updated_obj.id == created_id
        await session.commit()

    async with db_sessionmaker() as session:
        existing = await TagDAO.find_one_or_none(
            session=session, filters=_TagFilter(id=t1.id)
        )
        assert existing is not None
        count_updated = await TagDAO.bulk_update(
            session=session,
            records=[
                _TagBulk(id=t1.id, name=f"bulk_{uuid.uuid4().hex[:6]}"),
                _TagBulk(name="no_id_skip"),
            ],
        )
        assert count_updated == 1
        await session.commit()

    async with db_sessionmaker() as session:
        to_delete = await TagDAO.add(
            session=session, values=_TagAdd(name=f"del_{uuid.uuid4().hex[:6]}")
        )
        await session.flush()
        deleted = await TagDAO.delete(
            session=session, filters=_TagFilter(id=to_delete.id)
        )
        assert deleted == 1
        await session.commit()


@pytest.mark.asyncio
async def test_base_dao_delete_requires_filter(db_sessionmaker):
    """Функция: BaseDAO.delete (ветка ValueError при пустом фильтре)"""
    from app.api.models import Tag
    from app.dao.base import BaseDAO

    class TagDAO(BaseDAO[Tag]):
        model = Tag

    async with db_sessionmaker() as session:
        with pytest.raises(ValueError):
            await TagDAO.delete(session=session, filters=_EmptyFilters())
