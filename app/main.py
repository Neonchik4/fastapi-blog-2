from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.likes_router import router as router_likes
from app.api.router import router as router_api
from app.auth.router import router as router_auth
from app.dao.database import async_session_maker
from app.handlers import (
    _get_current_user_optional_from_request,
    _is_api_like_path,
    _wants_html,
    register_exception_handlers,
)
from app.pages.views import router as router_page
from app.stats.router import router as router_stats

# функции для тестов
__all__ = [
    "app",
    "async_session_maker",
    "_is_api_like_path",
    "_wants_html",
    "_get_current_user_optional_from_request",
]

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(router_auth)
app.include_router(router_api)
app.include_router(router_likes)
app.include_router(router_page)
app.include_router(router_stats)

register_exception_handlers(app, templates)
