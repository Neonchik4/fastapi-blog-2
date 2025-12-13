from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.likes_router import router as router_likes
from app.api.router import router as router_api
from app.auth.dao import UsersDAO
from app.auth.router import router as router_auth
from app.config import settings
from app.dao.database import async_session_maker
from app.pages.views import router as router_page
from app.stats.router import router as router_stats

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")

# Добавляем middleware для CORS
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


def _is_api_like_path(path: str) -> bool:
    if (
        path.startswith("/api")
        or path.startswith("/docs")
        or path.startswith("/openapi")
    ):
        return True
    if path.startswith("/auth/") and path != "/auth/":
        return True
    return False


def _wants_html(request: Request) -> bool:
    accept = (request.headers.get("accept") or "").lower()
    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" in accept or "application/json" in content_type:
        return False
    if "text/html" in accept:
        return True
    if accept.strip() == "" or "*/*" in accept:
        return True
    return False


async def _get_current_user_optional_from_request(request: Request):
    token = request.cookies.get("users_access_token")
    if not token:
        return None

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except JWTError:
        return None

    expire = payload.get("exp")
    if not expire:
        return None
    try:
        expire_time = datetime.fromtimestamp(int(expire), tz=timezone.utc)
    except Exception:
        return None
    if expire_time < datetime.now(timezone.utc):
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    try:
        async with async_session_maker() as session:
            return await UsersDAO.find_one_or_none_by_id(
                data_id=int(user_id), session=session
            )
    except Exception:
        return None


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if _is_api_like_path(request.url.path) or not _wants_html(request):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    if exc.status_code == 404:
        current_user = await _get_current_user_optional_from_request(request)
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "request": request,
                "current_user": current_user,
                "status_code": 404,
                "page_title": "Что-то пошло не так",
                "page_subtitle": "404 — страница не найдена.",
                "path": request.url.path,
            },
            status_code=404,
        )

    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "request": request,
            "current_user": await _get_current_user_optional_from_request(request),
            "status_code": exc.status_code,
            "page_title": "Что-то пошло не так",
            "page_subtitle": str(exc.detail),
            "path": request.url.path,
        },
        status_code=exc.status_code,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    if _is_api_like_path(request.url.path) or not _wants_html(request):
        return JSONResponse(
            status_code=500, content={"detail": "Internal Server Error"}
        )

    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "request": request,
            "current_user": await _get_current_user_optional_from_request(request),
            "status_code": 500,
            "page_title": "Что-то пошло не так",
            "page_subtitle": "500 — внутренняя ошибка сервера.",
            "path": request.url.path,
        },
        status_code=500,
    )
