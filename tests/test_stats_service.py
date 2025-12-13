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


def test_load_likes_branches(likes_json_file: Path):
    from app.stats.service import _load_likes

    likes_json_file.write_text("{", encoding="utf-8")
    assert _load_likes() == []

    likes_json_file.write_text(json.dumps({"x": 1}), encoding="utf-8")
    assert _load_likes() == []
    likes_json_file.write_text(
        json.dumps([{"user_id": 1}, 123, "x", {"post_id": 2}]), encoding="utf-8"
    )
    out = _load_likes()
    assert out == [{"user_id": 1}, {"post_id": 2}]


@pytest.mark.asyncio
async def test_compute_stats_empty_db_no_likes(db_sessionmaker, likes_json_file: Path):
    from app.stats.service import compute_stats

    likes_json_file.write_text("[]", encoding="utf-8")
    async with db_sessionmaker() as session:
        stats = await compute_stats(session)

    assert stats["users_total"] == 0
    assert stats["blogs_total"] == 0
    assert stats["tags_total"] == 0
    assert stats["roles_breakdown"] == []
    assert stats["blogs_by_status"] == []
    assert stats["top_authors"] == []
    assert stats["top_tags"] == []
    assert stats["avg_tags_per_blog"] == 0.0
    assert stats["likes_total"] == 0
    assert stats["unique_likers"] == 0
    assert stats["top_posts_by_likes"] == []


@pytest.mark.asyncio
async def test_compute_stats_with_data_and_likes(
    db_sessionmaker, ensure_user, set_user_role, likes_json_file: Path
):

    from app.api.models import Blog, BlogTag, Tag
    from app.stats.service import compute_stats

    u1 = await ensure_user(
        "s_u1@example.com",
        password="secret123",
        phone="+70000000011",
        first_name="Alice",
        last_name="One",
    )
    u2 = await ensure_user(
        "s_u2@example.com",
        password="secret123",
        phone="+70000000012",
        first_name="Bob",
        last_name="Two",
    )
    await set_user_role(u2.id, 3)
    u3 = await ensure_user(
        "s_u3@example.com",
        password="secret123",
        phone="+70000000013",
        first_name="Carol",
        last_name="Three",
    )

    async with db_sessionmaker() as session:
        b1 = Blog(
            title="Stats Post 1",
            author=u1.id,
            content="c1",
            short_description="s1",
            status="published",
        )
        b2 = Blog(
            title="Stats Post 2",
            author=u2.id,
            content="c2",
            short_description="s2",
            status="published",
        )
        b3 = Blog(
            title="Stats Draft",
            author=u1.id,
            content="c3",
            short_description="s3",
            status="draft",
        )
        session.add_all([b1, b2, b3])
        await session.flush()

        t1 = Tag(name="t_stats_1")
        t2 = Tag(name="t_stats_2")
        session.add_all([t1, t2])
        await session.flush()
        session.add_all(
            [
                BlogTag(blog_id=b1.id, tag_id=t1.id),
                BlogTag(blog_id=b1.id, tag_id=t2.id),
            ]
        )
        await session.commit()

    likes_json_file.write_text(
        json.dumps(
            [
                {"user_id": u1.id, "post_id": 999999, "liked": True},
                {"user_id": u1.id, "post_id": 123, "liked": False},
                {"user_id": str(u2.id), "post_id": b1.id, "liked": True},
                {"user_id": u1.id, "post_id": b1.id, "liked": True},
                {"user_id": u3.id, "post_id": b1.id, "liked": True},
                {"user_id": u3.id, "post_id": b2.id, "liked": True},
            ]
        ),
        encoding="utf-8",
    )

    async with db_sessionmaker() as session:
        stats = await compute_stats(session)

    assert stats["users_total"] == 3

    roles = {x["role"]: x["count"] for x in stats["roles_breakdown"]}
    assert roles.get("User") == 2
    assert roles.get("Admin") == 1

    assert stats["blogs_total"] == 3
    by_status = {x["status"]: x["count"] for x in stats["blogs_by_status"]}
    assert by_status.get("published") == 2
    assert by_status.get("draft") == 1

    assert stats["avg_tags_per_blog"] == 2.0
    assert stats["likes_total"] == 3
    assert stats["unique_likers"] == 2

    top = stats["top_posts_by_likes"]
    assert any(x["post_id"] == b1.id and x["likes"] == 2 for x in top)
    assert any(x["post_id"] == b2.id and x["likes"] == 1 for x in top)
    assert all("title" in x and x["title"] for x in top)
