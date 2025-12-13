from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dao import BlogDAO, BlogTagDAO, TagDAO
from app.api.schemas import (
    BlogCreateSchemaAdd,
    BlogCreateSchemaBase,
    BlogFullResponse,
    BlogNotFind,
)
from app.auth.dependencies import get_blog_info, get_current_user
from app.auth.models import User
from app.dao.session_maker import SessionDep, TransactionSessionDep

router = APIRouter(prefix="/api", tags=["API"])


@router.delete("/delete_blog/{blog_id}", summary="Удалить блог")
async def delete_blog(
    blog_id: int,
    session: AsyncSession = TransactionSessionDep,
    current_user: User = Depends(get_current_user),
):
    user_role_id = current_user.role.id if current_user.role else None
    result = await BlogDAO.delete_blog(session, blog_id, current_user.id, user_role_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.patch("/change_blog_status/{blog_id}", summary="Изменить статус блога")
async def change_blog_status(
    blog_id: int,
    new_status: str,
    session: AsyncSession = TransactionSessionDep,
    current_user: User = Depends(get_current_user),
):
    user_role_id = current_user.role.id if current_user.role else None
    result = await BlogDAO.change_blog_status(
        session, blog_id, new_status, current_user.id, user_role_id
    )
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/add_post/", summary="Добавление нового блога с тегами")
async def add_blog(
    add_data: BlogCreateSchemaBase,
    user_data: User = Depends(get_current_user),
    session: AsyncSession = TransactionSessionDep,
):
    blog_dict = add_data.model_dump()
    blog_dict["author"] = user_data.id
    tags = blog_dict.pop("tags", [])

    try:
        blog = await BlogDAO.add(
            session=session, values=BlogCreateSchemaAdd.model_validate(blog_dict)
        )
        blog_id = blog.id

        if tags:
            tags_ids = await TagDAO.add_tags(session=session, tag_names=tags)
            await BlogTagDAO.add_blog_tags(
                session=session,
                blog_tag_pairs=[{"blog_id": blog_id, "tag_id": i} for i in tags_ids],
            )

        return {
            "status": "success",
            "message": f"Блог с ID {blog_id} успешно добавлен с тегами.",
        }
    except IntegrityError as e:
        if "UNIQUE constraint failed" in str(e.orig):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Блог с таким заголовком уже существует.",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при добавлении блога.",
        )


@router.get("/get_blog/{blog_id}", summary="Получить информацию по блогу")
async def get_blog_endpoint(
    blog_id: int, blog_info: BlogFullResponse | BlogNotFind = Depends(get_blog_info)
) -> BlogFullResponse | BlogNotFind:
    return blog_info


@router.get("/blogs/", summary="Получить все блоги в статусе 'publish'")
async def get_blogs(
    author_id: int | None = None,
    tag: str | None = None,
    search: str | None = Query(
        None, description="Поиск по названию, описанию или контенту"
    ),
    page: int = Query(1, ge=1, description="Номер страницы"),
    page_size: int = Query(10, ge=10, le=100, description="Записей на странице"),
    session: AsyncSession = SessionDep,
):
    try:
        result = await BlogDAO.get_blog_list(
            session=session,
            author_id=author_id,
            tag=tag,
            search=search,
            page=page,
            page_size=page_size,
        )
        return (
            result
            if result["blogs"]
            else BlogNotFind(message="Блоги не найдены", status="error")
        )
    except Exception as e:
        logger.error(f"Ошибка при получении блогов: {e}")
        return JSONResponse(status_code=500, content={"detail": "Ошибка сервера"})
