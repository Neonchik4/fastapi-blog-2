from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dao import BlogDAO
from app.dao.session_maker import SessionDep

router = APIRouter(tags=["ФРОНТЕНД"])

templates = Jinja2Templates(directory="app/templates")


# Маршрут /blogs/{blog_id}/ перенесен в app/pages/views.py


@router.get("/blogs/")
async def get_blogs_page(
    request: Request,
    author_id: int | None = None,
    tag: str | None = None,
    page: int = 1,
    page_size: int = 3,
    session: AsyncSession = SessionDep,
):
    blogs = await BlogDAO.get_blog_list(
        session=session, author_id=author_id, tag=tag, page=page, page_size=page_size
    )
    return templates.TemplateResponse(
        request,
        "posts.html",
        {
            "request": request,
            "article": blogs,
            "filters": {
                "author_id": author_id,
                "tag": tag,
            },
        },
    )
