from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.models import Blog, BlogTag, Tag
from app.auth.models import Role, User


def _project_root() -> Path:
    # Получение корня проекта
    return Path(__file__).resolve().parents[2]


def _load_likes() -> list[dict[str, Any]]:
    likes_path = _project_root() / "data" / "likes.json"
    if not likes_path.exists():
        return []
    try:
        data = json.loads(likes_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
    except Exception:
        return []
    return []


async def compute_stats(session: AsyncSession) -> dict[str, Any]:
    # Метрики БД
    users_total = (await session.execute(select(func.count(User.id)))).scalar_one()

    roles_rows = (
        await session.execute(
            select(Role.name, func.count(User.id))
            .select_from(User)
            .join(Role, Role.id == User.role_id)
            .group_by(Role.name)
            .order_by(func.count(User.id).desc())
        )
    ).all()
    roles_breakdown = [{"role": name, "count": int(cnt)} for name, cnt in roles_rows]

    blogs_total = (await session.execute(select(func.count(Blog.id)))).scalar_one()

    blogs_status_rows = (
        await session.execute(
            select(Blog.status, func.count(Blog.id))
            .group_by(Blog.status)
            .order_by(func.count(Blog.id).desc())
        )
    ).all()
    blogs_by_status = [
        {"status": status, "count": int(cnt)} for status, cnt in blogs_status_rows
    ]

    top_authors_rows = (
        await session.execute(
            select(
                User.id,
                (User.first_name + " " + User.last_name).label("author_name"),
                func.count(Blog.id).label("posts_cnt"),
            )
            .select_from(Blog)
            .join(User, User.id == Blog.author)
            .group_by(User.id)
            .order_by(func.count(Blog.id).desc())
            .limit(10)
        )
    ).all()
    top_authors = [
        {"user_id": int(uid), "author_name": str(name), "posts_cnt": int(cnt)}
        for uid, name, cnt in top_authors_rows
    ]

    tags_total = (await session.execute(select(func.count(Tag.id)))).scalar_one()

    top_tags_rows = (
        await session.execute(
            select(Tag.name, func.count(BlogTag.tag_id).label("uses"))
            .select_from(BlogTag)
            .join(Tag, Tag.id == BlogTag.tag_id)
            .group_by(Tag.id)
            .order_by(func.count(BlogTag.tag_id).desc())
            .limit(10)
        )
    ).all()
    top_tags = [{"tag": str(name), "uses": int(uses)} for name, uses in top_tags_rows]

    # Среднее количество тегов на блог
    tag_cnt_subq = (
        select(BlogTag.blog_id, func.count(BlogTag.tag_id).label("tag_cnt"))
        .group_by(BlogTag.blog_id)
        .subquery()
    )
    avg_tags_per_blog = (
        await session.execute(select(func.avg(tag_cnt_subq.c.tag_cnt)))
    ).scalar_one()
    avg_tags_per_blog = (
        float(avg_tags_per_blog) if avg_tags_per_blog is not None else 0.0
    )

    # Метрики likes.json
    likes = _load_likes()
    liked_items = [
        x
        for x in likes
        if x.get("liked") is True
        and isinstance(x.get("user_id"), int)
        and isinstance(x.get("post_id"), int)
    ]

    existing_blog_ids_result = await session.execute(select(Blog.id))
    existing_blog_ids = {int(bid) for bid, in existing_blog_ids_result.all()}

    liked_items_existing = [
        x for x in liked_items if int(x.get("post_id", 0)) in existing_blog_ids
    ]

    likes_total = len(liked_items_existing)
    unique_likers = len({x["user_id"] for x in liked_items_existing})

    post_like_counts = Counter([x["post_id"] for x in liked_items_existing])
    top_posts = post_like_counts.most_common(10)
    top_post_ids = [post_id for post_id, _ in top_posts]

    titles_by_id: dict[int, str] = {}
    if top_post_ids:
        rows = (
            await session.execute(
                select(Blog.id, Blog.title).where(Blog.id.in_(top_post_ids))
            )
        ).all()
        titles_by_id = {int(bid): str(title) for bid, title in rows}

    # В статистику топа попадают только реально существующие блоги из БД
    top_posts_by_likes = [
        {"post_id": int(pid), "title": titles_by_id[int(pid)], "likes": int(cnt)}
        for pid, cnt in top_posts
        if int(pid) in titles_by_id
    ]

    return {
        "users_total": int(users_total),
        "roles_breakdown": roles_breakdown,
        "blogs_total": int(blogs_total),
        "blogs_by_status": blogs_by_status,
        "top_authors": top_authors,
        "tags_total": int(tags_total),
        "top_tags": top_tags,
        "avg_tags_per_blog": avg_tags_per_blog,
        "likes_total": likes_total,
        "unique_likers": unique_likers,
        "top_posts_by_likes": top_posts_by_likes,
    }
