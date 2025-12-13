import uuid

import pytest
from sqlalchemy.exc import SQLAlchemyError


async def _create_blog(
    session, *, author_id: int, title: str, status: str = "published"
):
    from app.api.models import Blog

    blog = Blog(
        title=title,
        author=author_id,
        content="Hello **world**",
        short_description="Short",
        status=status,
    )
    session.add(blog)
    await session.flush()
    return blog


@pytest.mark.asyncio
async def test_tagdao_add_tags_creates_and_reuses_existing(db_sessionmaker):
    """Функция: TagDAO.add_tags"""
    from sqlalchemy import select

    from app.api.dao import TagDAO
    from app.api.models import Tag

    async with db_sessionmaker() as session:
        ids1 = await TagDAO.add_tags(session=session, tag_names=["Python", "fastapi"])
        ids2 = await TagDAO.add_tags(session=session, tag_names=["python", "FASTAPI"])

        assert len(ids1) == 2
        assert ids1 == ids2  # должны переиспользовать существующие записи
        tags = (await session.execute(select(Tag).order_by(Tag.id))).scalars().all()
        assert [t.name for t in tags] == ["python", "fastapi"]


@pytest.mark.asyncio
async def test_tagdao_add_tags_rolls_back_on_flush_error(db_sessionmaker, monkeypatch):
    """Функция: TagDAO.add_tags (ветка SQLAlchemyError)"""
    from app.api.dao import TagDAO

    async with db_sessionmaker() as session:

        async def _boom():
            raise SQLAlchemyError("flush failed")

        monkeypatch.setattr(session, "flush", _boom)
        with pytest.raises(SQLAlchemyError):
            await TagDAO.add_tags(session=session, tag_names=["x"])


@pytest.mark.asyncio
async def test_blogdao_get_blog_list_filters_search_tag_and_paginates(
    db_sessionmaker, ensure_user
):
    """Функция: BlogDAO.get_blog_list"""
    from app.api.dao import BlogDAO, BlogTagDAO, TagDAO

    u1 = await ensure_user(
        f"u_{uuid.uuid4().hex[:8]}@example.com",
        password="secret123",
        phone=f"+7{uuid.uuid4().int % 10**10:010d}",
        first_name="Alice",
        last_name="Wonder",
    )

    async with db_sessionmaker() as session:
        b1 = await _create_blog(
            session,
            author_id=u1.id,
            title=f"T1_{uuid.uuid4().hex[:6]}",
            status="published",
        )
        b2 = await _create_blog(
            session,
            author_id=u1.id,
            title=f"T2_{uuid.uuid4().hex[:6]}",
            status="published",
        )
        await _create_blog(
            session, author_id=u1.id, title=f"D_{uuid.uuid4().hex[:6]}", status="draft"
        )

        tag_ids = await TagDAO.add_tags(
            session=session, tag_names=["fastapi", "python"]
        )
        await BlogTagDAO.add_blog_tags(
            session=session,
            blog_tag_pairs=[
                {"blog_id": b1.id, "tag_id": tag_ids[0]},
                {"blog_id": b1.id, "tag_id": tag_ids[1]},
            ],
        )

        await session.commit()

    async with db_sessionmaker() as session:
        r = await BlogDAO.get_blog_list(session=session, page=0, page_size=1)
        assert r["page"] == 1
        assert r["total_result"] >= 2
        assert all(b.status == "published" for b in r["blogs"])

        r2 = await BlogDAO.get_blog_list(session=session, author_id=u1.id)
        assert r2["total_result"] >= 2

        r3 = await BlogDAO.get_blog_list(session=session, search=b2.title)
        assert any(b.title == b2.title for b in r3["blogs"])

        r4 = await BlogDAO.get_blog_list(session=session, search="Alice")
        assert any(b.title in {b1.title, b2.title} for b in r4["blogs"])

        r5 = await BlogDAO.get_blog_list(session=session, tag="fastapi")
        ids = [b.id for b in r5["blogs"]]
        assert len(ids) == len(set(ids))
        assert b1.id in ids


@pytest.mark.asyncio
async def test_blogdao_get_blog_list_returns_empty_when_no_published(
    db_sessionmaker, ensure_user
):
    """Функция: BlogDAO.get_blog_list (ветка total_result == 0)"""
    from app.api.dao import BlogDAO

    u1 = await ensure_user(
        f"u_{uuid.uuid4().hex[:8]}@example.com",
        password="secret123",
        phone=f"+7{uuid.uuid4().int % 10**10:010d}",
    )

    async with db_sessionmaker() as session:
        await _create_blog(
            session, author_id=u1.id, title=f"D_{uuid.uuid4().hex[:6]}", status="draft"
        )
        await session.commit()

    async with db_sessionmaker() as session:
        r = await BlogDAO.get_blog_list(session=session)
        assert r == {"page": 1, "total_page": 0, "total_result": 0, "blogs": []}


@pytest.mark.asyncio
async def test_blogdao_get_draft_blogs_author_and_all(db_sessionmaker, ensure_user):
    """Функция: BlogDAO.get_draft_blogs"""
    from app.api.dao import BlogDAO

    u1 = await ensure_user(
        f"u_{uuid.uuid4().hex[:8]}@example.com",
        password="secret123",
        phone=f"+7{uuid.uuid4().int % 10**10:010d}",
    )
    u2 = await ensure_user(
        f"u_{uuid.uuid4().hex[:8]}@example.com",
        password="secret123",
        phone=f"+7{uuid.uuid4().int % 10**10:010d}",
    )

    async with db_sessionmaker() as session:
        d1 = await _create_blog(
            session, author_id=u1.id, title=f"D1_{uuid.uuid4().hex[:6]}", status="draft"
        )
        await _create_blog(
            session, author_id=u2.id, title=f"D2_{uuid.uuid4().hex[:6]}", status="draft"
        )
        await session.commit()

    async with db_sessionmaker() as session:
        r = await BlogDAO.get_draft_blogs(
            session=session, author_id=u1.id, page=0, page_size=1
        )
        assert r["page"] == 1
        assert any(b.id == d1.id for b in r["blogs"])

        r2 = await BlogDAO.get_draft_blogs(session=session, author_id=None)
        assert r2["total_result"] >= 2


@pytest.mark.asyncio
async def test_blogdao_get_full_blog_info_access_rules(db_sessionmaker, ensure_user):
    """Функция: BlogDAO.get_full_blog_info"""
    from app.api.dao import BlogDAO

    author = await ensure_user(
        f"u_{uuid.uuid4().hex[:8]}@example.com",
        password="secret123",
        phone=f"+7{uuid.uuid4().int % 10**10:010d}",
    )
    other = await ensure_user(
        f"u_{uuid.uuid4().hex[:8]}@example.com",
        password="secret123",
        phone=f"+7{uuid.uuid4().int % 10**10:010d}",
    )

    async with db_sessionmaker() as session:
        draft = await _create_blog(
            session,
            author_id=author.id,
            title=f"D_{uuid.uuid4().hex[:6]}",
            status="draft",
        )
        pub = await _create_blog(
            session,
            author_id=author.id,
            title=f"P_{uuid.uuid4().hex[:6]}",
            status="published",
        )
        await session.commit()

    async with db_sessionmaker() as session:
        not_found = await BlogDAO.get_full_blog_info(session=session, blog_id=999999)
        assert isinstance(not_found, dict) and not_found["status"] == "error"

        denied = await BlogDAO.get_full_blog_info(
            session=session, blog_id=draft.id, author_id=other.id, user_role_id=1
        )
        assert isinstance(denied, dict) and denied["status"] == "error"

        allowed_author = await BlogDAO.get_full_blog_info(
            session=session, blog_id=draft.id, author_id=author.id, user_role_id=1
        )
        assert getattr(allowed_author, "id", None) == draft.id

        allowed_admin = await BlogDAO.get_full_blog_info(
            session=session, blog_id=draft.id, author_id=other.id, user_role_id=3
        )
        assert getattr(allowed_admin, "id", None) == draft.id

        allowed_published = await BlogDAO.get_full_blog_info(
            session=session, blog_id=pub.id, author_id=None, user_role_id=None
        )
        assert getattr(allowed_published, "id", None) == pub.id


@pytest.mark.asyncio
async def test_blogdao_change_blog_status_and_delete_blog_edge_cases(
    db_sessionmaker, ensure_user
):
    """Функции: BlogDAO.change_blog_status / BlogDAO.delete_blog"""
    from app.api.dao import BlogDAO

    author = await ensure_user(
        f"u_{uuid.uuid4().hex[:8]}@example.com",
        password="secret123",
        phone=f"+7{uuid.uuid4().int % 10**10:010d}",
    )
    other = await ensure_user(
        f"u_{uuid.uuid4().hex[:8]}@example.com",
        password="secret123",
        phone=f"+7{uuid.uuid4().int % 10**10:010d}",
    )

    async with db_sessionmaker() as session:
        blog = await _create_blog(
            session,
            author_id=author.id,
            title=f"P_{uuid.uuid4().hex[:6]}",
            status="published",
        )
        await session.commit()

    async with db_sessionmaker() as session:
        bad_status = await BlogDAO.change_blog_status(
            session, blog.id, "invalid", author.id, 1
        )
        assert bad_status["status"] == "error"

        not_found = await BlogDAO.change_blog_status(
            session, 999999, "draft", author.id, 1
        )
        assert not_found["status"] == "error"

        forbidden = await BlogDAO.change_blog_status(
            session, blog.id, "draft", other.id, 1
        )
        assert forbidden["status"] == "error"

        info = await BlogDAO.change_blog_status(
            session, blog.id, "published", author.id, 1
        )
        assert info["status"] == "info"

        ok = await BlogDAO.change_blog_status(session, blog.id, "draft", author.id, 1)
        assert ok["status"] == "success"

        del_forbidden = await BlogDAO.delete_blog(session, blog.id, other.id, 1)
        assert del_forbidden["status"] == "error"

        del_ok = await BlogDAO.delete_blog(session, blog.id, author.id, 1)
        assert del_ok["status"] == "success"


@pytest.mark.asyncio
async def test_blogdao_change_status_returns_error_on_sqlalchemy_error(
    db_sessionmaker, ensure_user, monkeypatch
):
    """Функция: BlogDAO.change_blog_status (ветка except SQLAlchemyError)"""
    from app.api.dao import BlogDAO

    author = await ensure_user(
        f"u_{uuid.uuid4().hex[:8]}@example.com",
        password="secret123",
        phone=f"+7{uuid.uuid4().int % 10**10:010d}",
    )

    async with db_sessionmaker() as session:
        blog = await _create_blog(
            session,
            author_id=author.id,
            title=f"P_{uuid.uuid4().hex[:6]}",
            status="published",
        )
        await session.commit()

    async with db_sessionmaker() as session:

        async def _boom(*args, **kwargs):
            raise SQLAlchemyError("db broken")

        monkeypatch.setattr(session, "execute", _boom)
        r = await BlogDAO.change_blog_status(session, blog.id, "draft", author.id, 1)
        assert r["status"] == "error"


@pytest.mark.asyncio
async def test_blogdao_get_liked_blogs_empty_and_nonempty(db_sessionmaker, ensure_user):
    """Функция: BlogDAO.get_liked_blogs"""
    from app.api.dao import BlogDAO

    author = await ensure_user(
        f"u_{uuid.uuid4().hex[:8]}@example.com",
        password="secret123",
        phone=f"+7{uuid.uuid4().int % 10**10:010d}",
    )

    async with db_sessionmaker() as session:
        pub = await _create_blog(
            session,
            author_id=author.id,
            title=f"P_{uuid.uuid4().hex[:6]}",
            status="published",
        )
        await _create_blog(
            session,
            author_id=author.id,
            title=f"D_{uuid.uuid4().hex[:6]}",
            status="draft",
        )
        await session.commit()

    async with db_sessionmaker() as session:
        empty = await BlogDAO.get_liked_blogs(session=session, post_ids=[])
        assert empty["total_result"] == 0 and empty["blogs"] == []

        r = await BlogDAO.get_liked_blogs(
            session=session, post_ids=[pub.id], page=0, page_size=1
        )
        assert r["page"] == 1
        assert any(b.id == pub.id for b in r["blogs"])


@pytest.mark.asyncio
async def test_blogtagdao_add_blog_tags_handles_invalid_pairs_and_flush_error(
    db_sessionmaker, ensure_user, monkeypatch
):
    """Функция: BlogTagDAO.add_blog_tags"""
    from app.api.dao import BlogTagDAO, TagDAO

    author = await ensure_user(
        f"u_{uuid.uuid4().hex[:8]}@example.com",
        password="secret123",
        phone=f"+7{uuid.uuid4().int % 10**10:010d}",
    )

    async with db_sessionmaker() as session:
        blog = await _create_blog(
            session,
            author_id=author.id,
            title=f"P_{uuid.uuid4().hex[:6]}",
            status="published",
        )
        tag_ids = await TagDAO.add_tags(session=session, tag_names=["t1"])

        await BlogTagDAO.add_blog_tags(
            session=session, blog_tag_pairs=[{"blog_id": None, "tag_id": None}]
        )
        await BlogTagDAO.add_blog_tags(session=session, blog_tag_pairs=[])

        async def _boom():
            raise SQLAlchemyError("flush failed")

        monkeypatch.setattr(session, "flush", _boom)
        with pytest.raises(SQLAlchemyError):
            await BlogTagDAO.add_blog_tags(
                session=session,
                blog_tag_pairs=[{"blog_id": blog.id, "tag_id": tag_ids[0]}],
            )
