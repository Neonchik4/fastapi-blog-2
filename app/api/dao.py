from typing import Optional

from loguru import logger
from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.api.models import Blog, BlogTag, Tag
from app.api.schemas import BlogFullResponse
from app.auth.models import User
from app.dao.base import BaseDAO


class TagDAO(BaseDAO):
    model = Tag

    @classmethod
    async def add_tags(cls, session: AsyncSession, tag_names: list[str]) -> list[int]:
        """Добавление тегов в БД, возвращает список ID."""
        tag_ids = []
        for tag_name in tag_names:
            tag_name = tag_name.lower()
            stmt = select(cls.model).filter_by(name=tag_name)
            result = await session.execute(stmt)
            tag = result.scalars().first()

            if tag:
                tag_ids.append(tag.id)
            else:
                new_tag = cls.model(name=tag_name)
                session.add(new_tag)
                try:
                    await session.flush()
                    logger.info(f"Тег '{tag_name}' добавлен в базу данных.")
                    tag_ids.append(new_tag.id)
                except SQLAlchemyError as e:
                    await session.rollback()
                    logger.error(f"Ошибка при добавлении тега '{tag_name}': {e}")
                    raise e

        return tag_ids


class BlogDAO(BaseDAO):
    model = Blog

    @classmethod
    async def get_blog_list(
        cls,
        session: AsyncSession,
        author_id: Optional[int] = None,
        tag: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
    ):
        """Получение списка опубликованных блогов с фильтрацией и пагинацией."""
        page_size = max(3, min(page_size, 100))
        page = max(1, page)

        base_query = (
            select(cls.model)
            .options(joinedload(cls.model.user), selectinload(cls.model.tags))
            .filter_by(status="published")
        )

        if author_id is not None:
            base_query = base_query.filter_by(author=author_id)

        if search:
            search = search.strip()
            base_query = base_query.filter(
                or_(
                    cls.model.title.ilike(f"%{search}%"),
                    cls.model.short_description.ilike(f"%{search}%"),
                    cls.model.content.ilike(f"%{search}%"),
                    cls.model.user.has(
                        or_(
                            User.first_name.ilike(f"%{search}%"),
                            User.last_name.ilike(f"%{search}%"),
                            (User.first_name + " " + User.last_name).ilike(
                                f"%{search}%"
                            ),
                        )
                    ),
                    cls.model.tags.any(Tag.name.ilike(f"%{search.lower()}%")),
                )
            )

        if tag:
            base_query = base_query.join(cls.model.tags).filter(
                cls.model.tags.any(Tag.name.ilike(f"%{tag.lower()}%"))
            )

        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await session.scalar(count_query)

        if not total_result:
            return {"page": page, "total_page": 0, "total_result": 0, "blogs": []}

        total_page = (total_result + page_size - 1) // page_size

        offset = (page - 1) * page_size
        paginated_query = base_query.offset(offset).limit(page_size)

        result = await session.execute(paginated_query)
        blogs = result.scalars().all()

        unique_blogs = []
        seen_ids = set()
        for blog in blogs:
            if blog.id not in seen_ids:
                unique_blogs.append(BlogFullResponse.model_validate(blog))
                seen_ids.add(blog.id)

        filters = []
        if author_id is not None:
            filters.append(f"author_id={author_id}")
        if tag:
            filters.append(f"tag={tag}")
        if search:
            filters.append(f"search={search}")
        filter_str = " & ".join(filters) if filters else "no filters"

        logger.info(
            f"Страница {page} получена с {len(blogs)} блогами, фильтры: {filter_str}"
        )
        return {
            "page": page,
            "total_page": total_page,
            "total_result": total_result,
            "blogs": unique_blogs,
        }

    @classmethod
    async def get_draft_blogs(
        cls,
        session: AsyncSession,
        author_id: int | None = None,
        page: int = 1,
        page_size: int = 10,
    ):
        """Получение списка черновиков с пагинацией."""
        page_size = max(3, min(page_size, 100))
        page = max(1, page)

        base_query = (
            select(cls.model)
            .options(joinedload(cls.model.user), selectinload(cls.model.tags))
            .filter_by(status="draft")
        )

        if author_id is not None:
            base_query = base_query.filter_by(author=author_id)

        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await session.scalar(count_query)

        if not total_result:
            return {"page": page, "total_page": 0, "total_result": 0, "blogs": []}

        total_page = (total_result + page_size - 1) // page_size
        offset = (page - 1) * page_size
        paginated_query = base_query.offset(offset).limit(page_size)

        result = await session.execute(paginated_query)
        blogs = result.scalars().all()

        unique_blogs = []
        seen_ids = set()
        for blog in blogs:
            if blog.id not in seen_ids:
                unique_blogs.append(BlogFullResponse.model_validate(blog))
                seen_ids.add(blog.id)

        return {
            "page": page,
            "total_page": total_page,
            "total_result": total_result,
            "blogs": unique_blogs,
        }

    @classmethod
    async def get_full_blog_info(
        cls,
        session: AsyncSession,
        blog_id: int,
        author_id: int | None = None,
        user_role_id: int | None = None,
    ):
        """Получение полной информации о блоге с проверкой прав доступа."""
        query = (
            select(cls.model)
            .options(joinedload(Blog.user), selectinload(Blog.tags))
            .filter_by(id=blog_id)
        )

        result = await session.execute(query)
        blog = result.scalar_one_or_none()

        if not blog:
            return {
                "message": f"Блог с ID {blog_id} не найден или у вас нет прав на его просмотр.",
                "status": "error",
            }

        if blog.status == "draft":
            is_author = author_id == blog.author
            is_admin = user_role_id in [3, 4]

            if not (is_author or is_admin):
                return {
                    "message": "Этот блог находится в статусе черновика, и доступ к нему имеют только авторы и администраторы.",
                    "status": "error",
                }

        return blog

    @classmethod
    async def change_blog_status(
        cls,
        session: AsyncSession,
        blog_id: int,
        new_status: str,
        author_id: int,
        user_role_id: int | None = None,
    ) -> dict:
        """Изменение статуса блога автором или админом."""
        if new_status not in ["draft", "published"]:
            return {
                "message": "Недопустимый статус. Используйте 'draft' или 'published'.",
                "status": "error",
            }

        try:
            query = select(cls.model).filter_by(id=blog_id)
            result = await session.execute(query)
            blog = result.scalar_one_or_none()

            if not blog:
                return {"message": f"Блог с ID {blog_id} не найден.", "status": "error"}

            is_admin = user_role_id in [3, 4]
            if blog.author != author_id and not is_admin:
                return {
                    "message": "У вас нет прав на изменение статуса этого блога.",
                    "status": "error",
                }

            if blog.status == new_status:
                return {
                    "message": f"Блог уже имеет статус '{new_status}'.",
                    "status": "info",
                    "blog_id": blog_id,
                    "current_status": new_status,
                }

            blog.status = new_status
            await session.flush()

            return {
                "message": f"Статус блога успешно изменен на '{new_status}'.",
                "status": "success",
                "blog_id": blog_id,
                "new_status": new_status,
            }

        except SQLAlchemyError as e:
            await session.rollback()
            return {
                "message": f"Произошла ошибка при изменении статуса блога: {str(e)}",
                "status": "error",
            }

    @classmethod
    async def delete_blog(
        cls,
        session: AsyncSession,
        blog_id: int,
        author_id: int,
        user_role_id: int | None = None,
    ) -> dict:
        """Удаление блога автором или админом."""
        try:
            query = select(cls.model).filter_by(id=blog_id)
            result = await session.execute(query)
            blog = result.scalar_one_or_none()

            if not blog:
                return {"message": f"Блог с ID {blog_id} не найден.", "status": "error"}

            is_admin = user_role_id in [3, 4]
            if blog.author != author_id and not is_admin:
                return {
                    "message": "У вас нет прав на удаление этого блога.",
                    "status": "error",
                }

            await session.delete(blog)
            await session.flush()

            return {
                "message": f"Блог с ID {blog_id} успешно удален.",
                "status": "success",
            }

        except SQLAlchemyError as e:
            await session.rollback()
            return {
                "message": f"Произошла ошибка при удалении блога: {str(e)}",
                "status": "error",
            }

    @classmethod
    async def get_liked_blogs(
        cls,
        session: AsyncSession,
        post_ids: list[int],
        page: int = 1,
        page_size: int = 6,
    ):
        """Получение списка блогов по ID с пагинацией."""
        if not post_ids:
            return {"page": page, "total_page": 0, "total_result": 0, "blogs": []}

        page_size = max(3, min(page_size, 100))
        page = max(1, page)

        base_query = (
            select(cls.model)
            .options(joinedload(cls.model.user), selectinload(cls.model.tags))
            .filter(cls.model.id.in_(post_ids), cls.model.status == "published")
        )

        count_query = select(func.count()).select_from(
            select(cls.model)
            .filter(cls.model.id.in_(post_ids), cls.model.status == "published")
            .subquery()
        )
        total_result = await session.scalar(count_query)

        if not total_result:
            return {"page": page, "total_page": 0, "total_result": 0, "blogs": []}

        total_page = (total_result + page_size - 1) // page_size

        offset = (page - 1) * page_size
        paginated_query = base_query.offset(offset).limit(page_size)

        result = await session.execute(paginated_query)
        blogs = result.scalars().all()

        unique_blogs = []
        seen_ids = set()
        for blog in blogs:
            if blog.id not in seen_ids:
                unique_blogs.append(BlogFullResponse.model_validate(blog))
                seen_ids.add(blog.id)

        logger.info(
            f"Страница {page} получена с {len(unique_blogs)} понравившимися блогами"
        )

        return {
            "page": page,
            "total_page": total_page,
            "total_result": total_result,
            "blogs": unique_blogs,
        }


class BlogTagDAO(BaseDAO):
    model = BlogTag

    @classmethod
    async def add_blog_tags(
        cls, session: AsyncSession, blog_tag_pairs: list[dict]
    ) -> None:
        """Массовое добавление связок блогов и тегов."""
        blog_tag_instances = []
        for pair in blog_tag_pairs:
            blog_id = pair.get("blog_id")
            tag_id = pair.get("tag_id")
            if blog_id and tag_id:
                blog_tag = cls.model(blog_id=blog_id, tag_id=tag_id)
                blog_tag_instances.append(blog_tag)
            else:
                logger.warning(f"Пропущен неверный параметр в паре: {pair}")

        if blog_tag_instances:
            session.add_all(blog_tag_instances)
            try:
                await session.flush()
                logger.info(
                    f"{len(blog_tag_instances)} связок блогов и тегов успешно добавлено."
                )
            except SQLAlchemyError as e:
                await session.rollback()
                logger.error(f"Ошибка при добавлении связок блогов и тегов: {e}")
                raise e
        else:
            logger.warning("Нет валидных данных для добавления в таблицу blog_tags.")
