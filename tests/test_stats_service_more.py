import json
from pathlib import Path

import pytest


@pytest.fixture
def likes_json_file():
    """
    `app.stats.service._load_likes()` читает `data/likes.json` относительно корня проекта.
    Безопасно подменяем содержимое файла и восстанавливаем обратно.
    """
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


def test_load_likes_file_not_exists(likes_json_file: Path):
    """Тест: файл не существует -> возвращает []"""
    from app.stats.service import _load_likes

    if likes_json_file.exists():
        likes_json_file.unlink()
    assert _load_likes() == []


def test_load_likes_empty_list(likes_json_file: Path):
    """Тест: файл содержит пустой список -> возвращает []"""
    from app.stats.service import _load_likes

    likes_json_file.write_text("[]", encoding="utf-8")
    assert _load_likes() == []


@pytest.mark.asyncio
async def test_compute_stats_no_tags_avg_is_zero(
    db_sessionmaker, ensure_user, likes_json_file: Path
):
    """Тест: если нет блогов с тегами, avg_tags_per_blog = 0.0"""
    from app.api.models import Blog
    from app.stats.service import compute_stats

    u = await ensure_user(
        "stats_no_tags@example.com",
        password="secret123",
        phone="+70000000020",
    )

    async with db_sessionmaker() as session:
        # Блог без тегов
        blog = Blog(
            title="No Tags Blog",
            author=u.id,
            content="Content",
            short_description="Short",
            status="published",
        )
        session.add(blog)
        await session.commit()

    likes_json_file.write_text("[]", encoding="utf-8")
    async with db_sessionmaker() as session:
        stats = await compute_stats(session)

    assert stats["avg_tags_per_blog"] == 0.0


@pytest.mark.asyncio
async def test_compute_stats_top_posts_empty_list_when_no_likes(
    db_sessionmaker, ensure_user, likes_json_file: Path
):
    """Тест: если top_post_ids пустой, titles_by_id не запрашивается"""
    from app.stats.service import compute_stats

    await ensure_user(
        "stats_no_likes@example.com",
        password="secret123",
        phone="+70000000021",
    )

    likes_json_file.write_text("[]", encoding="utf-8")
    async with db_sessionmaker() as session:
        stats = await compute_stats(session)

    assert stats["top_posts_by_likes"] == []


@pytest.mark.asyncio
async def test_compute_stats_likes_filter_invalid_types(
    db_sessionmaker, ensure_user, likes_json_file: Path
):
    """Тест: фильтрация лайков по типам (liked=True, int user_id, int post_id)"""
    from app.api.models import Blog
    from app.stats.service import compute_stats

    u = await ensure_user(
        "stats_filter@example.com",
        password="secret123",
        phone="+70000000022",
    )

    async with db_sessionmaker() as session:
        blog = Blog(
            title="Filter Blog",
            author=u.id,
            content="Content",
            short_description="Short",
            status="published",
        )
        session.add(blog)
        await session.flush()
        blog_id = blog.id
        await session.commit()

    # Разные комбинации невалидных данных
    likes_json_file.write_text(
        json.dumps(
            [
                {
                    "user_id": "not_int",
                    "post_id": blog_id,
                    "liked": True,
                },
                {
                    "user_id": u.id,
                    "post_id": "not_int",
                    "liked": True,
                },
                {"user_id": u.id, "post_id": blog_id, "liked": False},
                {"user_id": u.id, "post_id": blog_id, "liked": True},  # валидный
            ]
        ),
        encoding="utf-8",
    )

    async with db_sessionmaker() as session:
        stats = await compute_stats(session)

    # Только один валидный лайк должен быть учтён
    assert stats["likes_total"] == 1
    assert stats["unique_likers"] == 1


@pytest.mark.asyncio
async def test_compute_stats_top_posts_filters_nonexistent(
    db_sessionmaker, ensure_user, likes_json_file: Path
):
    """Тест: top_posts_by_likes исключает посты, которых нет в БД"""
    from app.api.models import Blog
    from app.stats.service import compute_stats

    u = await ensure_user(
        "stats_filter_posts@example.com",
        password="secret123",
        phone="+70000000023",
    )

    async with db_sessionmaker() as session:
        blog = Blog(
            title="Real Blog",
            author=u.id,
            content="Content",
            short_description="Short",
            status="published",
        )
        session.add(blog)
        await session.flush()
        blog_id = blog.id
        await session.commit()

    # Лайки на существующий и несуществующий пост
    likes_json_file.write_text(
        json.dumps(
            [
                {"user_id": u.id, "post_id": 999999, "liked": True},  # не существует
                {"user_id": u.id, "post_id": blog_id, "liked": True},  # существует
            ]
        ),
        encoding="utf-8",
    )

    async with db_sessionmaker() as session:
        stats = await compute_stats(session)

    # В топе должен быть только существующий пост
    top = stats["top_posts_by_likes"]
    assert len(top) == 1
    assert top[0]["post_id"] == blog_id
    assert "title" in top[0]


@pytest.mark.asyncio
async def test_compute_stats_top_posts_empty_list_skips_query(
    db_sessionmaker, ensure_user, likes_json_file: Path
):
    """Тест: если top_post_ids пустой, запрос titles_by_id не выполняется"""
    from app.stats.service import compute_stats

    await ensure_user(
        "stats_empty_top@example.com",
        password="secret123",
        phone="+70000000024",
    )

    likes_json_file.write_text("[]", encoding="utf-8")

    async with db_sessionmaker() as session:
        stats = await compute_stats(session)

    assert stats["top_posts_by_likes"] == []
    assert stats["likes_total"] == 0


@pytest.mark.asyncio
async def test_load_likes_file_not_exists_returns_empty(likes_json_file: Path):
    """Тест: _load_likes когда файл не существует -> []"""
    from app.stats.service import _load_likes

    if likes_json_file.exists():
        likes_json_file.unlink()

    result = _load_likes()
    assert result == []


@pytest.mark.asyncio
async def test_load_likes_invalid_json_returns_empty(likes_json_file: Path):
    """Тест: _load_likes при невалидном JSON -> []"""
    from app.stats.service import _load_likes

    likes_json_file.write_text("{ invalid json", encoding="utf-8")
    result = _load_likes()
    assert result == []


@pytest.mark.asyncio
async def test_load_likes_not_list_returns_empty(likes_json_file: Path):
    """Тест: _load_likes когда JSON не список -> []"""
    from app.stats.service import _load_likes

    likes_json_file.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    result = _load_likes()
    assert result == []


@pytest.mark.asyncio
async def test_load_likes_filters_non_dict_items(likes_json_file: Path):
    """Тест: _load_likes фильтрует элементы, которые не dict"""
    from app.stats.service import _load_likes

    likes_json_file.write_text(
        json.dumps([{"user_id": 1}, 123, "string", {"post_id": 2}, None, []]),
        encoding="utf-8",
    )
    result = _load_likes()
    assert result == [{"user_id": 1}, {"post_id": 2}]
