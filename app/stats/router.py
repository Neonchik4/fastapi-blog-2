from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.dao.session_maker import SessionDep
from app.stats.service import compute_stats

router = APIRouter(tags=["СТАТИСТИКА"])
templates = Jinja2Templates(directory="app/templates")


def _build_common_context(request: Request, current_user: User):
    return {"request": request, "current_user": current_user}


@router.get("/stats/")
async def stats_page(
    request: Request,
    user_data: User = Depends(get_current_user),
    session: AsyncSession = SessionDep,
):
    stats = await compute_stats(session)
    context = {**_build_common_context(request, user_data), "stats": stats}
    return templates.TemplateResponse(request, "stats.html", context)


@router.get("/api/stats/")
async def stats_api(
    user_data: User = Depends(get_current_user),
    session: AsyncSession = SessionDep,
):
    stats = await compute_stats(session)
    return JSONResponse(content={"ok": True, "stats": stats})
