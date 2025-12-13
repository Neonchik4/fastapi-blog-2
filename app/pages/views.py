import markdown2
from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dao import BlogDAO, BlogTagDAO, TagDAO
from app.api.schemas import (
    BlogCreateSchemaAdd,
    BlogCreateSchemaBase,
    BlogFullResponse,
    BlogNotFind,
)
from app.auth.auth import authenticate_user, create_access_token
from app.auth.dao import RoleDAO, UsersDAO
from app.auth.dependencies import (
    get_blog_info,
    get_current_user,
    get_current_user_optional,
)
from app.auth.models import User
from app.auth.schemas import (
    EmailModel,
    PhoneModel,
    SUserAddDB,
    SUserRegister,
    SUserUpdate,
)
from app.dao.session_maker import SessionDep, TransactionSessionDep

router = APIRouter(tags=["ФРОНТЕНД"])
templates = Jinja2Templates(directory="app/templates")


def _build_common_context(request: Request, current_user: User | None):
    return {"request": request, "current_user": current_user}


@router.get("/")
async def home_page(
    request: Request,
    search: str | None = None,
    tag: str | None = None,
    page: int = 1,
    page_size: int = 5,
    session: AsyncSession = SessionDep,
    user_data: User | None = Depends(get_current_user_optional),
):
    blogs = await BlogDAO.get_blog_list(
        session=session, tag=tag, search=search, page=page, page_size=page_size
    )
    context = {
        **_build_common_context(request, user_data),
        "article": blogs,
        "filters": {"tag": tag, "search": search},
    }
    return templates.TemplateResponse(request, "home.html", context)


@router.get("/blogs/create/")
async def create_blog_page(
    request: Request,
    user_data: User = Depends(get_current_user),
):
    context = {
        **_build_common_context(request, user_data),
        "form_error": None,
    }
    return templates.TemplateResponse(request, "create_blog.html", context)


@router.post("/blogs/create/")
async def create_blog_submit(
    request: Request,
    user_data: User = Depends(get_current_user),
    session: AsyncSession = TransactionSessionDep,
):
    form = await request.form()
    tags_raw = form.get("tags") or ""
    tags = [tag.strip() for tag in tags_raw.split(",") if tag.strip()]

    try:
        blog_base = BlogCreateSchemaBase(
            title=(form.get("title") or "").strip(),
            content=(form.get("content") or "").strip(),
            short_description=(form.get("short_description") or "").strip(),
            tags=tags,
        )
    except ValidationError as exc:
        errors = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in exc.errors()])
        context = {
            **_build_common_context(request, user_data),
            "form_error": f"Ошибка валидации: {errors}",
        }
        return templates.TemplateResponse(
            request,
            "create_blog.html",
            context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    blog_payload = blog_base.model_dump()
    blog_payload["author"] = user_data.id
    tags_list = blog_payload.pop("tags", [])

    try:
        blog = await BlogDAO.add(
            session=session, values=BlogCreateSchemaAdd.model_validate(blog_payload)
        )
        if tags_list:
            tags_ids = await TagDAO.add_tags(
                session=session, tag_names=[tag.lower() for tag in tags_list]
            )
            await BlogTagDAO.add_blog_tags(
                session=session,
                blog_tag_pairs=[
                    {"blog_id": blog.id, "tag_id": tid} for tid in tags_ids
                ],
            )
    except IntegrityError:
        context = {
            **_build_common_context(request, user_data),
            "form_error": "Блог с таким заголовком уже существует",
        }
        return templates.TemplateResponse(
            request,
            "create_blog.html",
            context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url=f"/blogs/{blog.id}/", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/blogs/{blog_id}/edit/")
async def edit_blog_page(
    request: Request,
    blog_id: int,
    session: AsyncSession = SessionDep,
    user_data: User = Depends(get_current_user),
):
    user_role_id = user_data.role.id if user_data.role else None
    blog_obj = await BlogDAO.get_full_blog_info(
        session=session,
        blog_id=blog_id,
        author_id=user_data.id,
        user_role_id=user_role_id,
    )
    if isinstance(blog_obj, dict):
        return templates.TemplateResponse(
            request,
            "404.html",
            {"request": request, "blog_id": blog_id, "current_user": user_data},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    is_admin = user_data.role.id in [3, 4] if user_data.role else False
    if (blog_obj.author != user_data.id) and not is_admin:
        return templates.TemplateResponse(
            request,
            "404.html",
            {"request": request, "blog_id": blog_id, "current_user": user_data},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    blog = BlogFullResponse.model_validate(blog_obj).model_dump()
    tags_str = (
        ", ".join([tag["name"] for tag in blog.get("tags", [])])
        if blog.get("tags")
        else ""
    )
    context = {
        **_build_common_context(request, user_data),
        "blog": blog,
        "tags_str": tags_str,
        "form_error": None,
    }
    return templates.TemplateResponse(request, "edit_blog.html", context)


@router.post("/blogs/{blog_id}/edit/")
async def edit_blog_submit(
    request: Request,
    blog_id: int,
    user_data: User = Depends(get_current_user),
    session: AsyncSession = TransactionSessionDep,
):
    form = await request.form()
    tags_raw = form.get("tags") or ""
    tags = [tag.strip() for tag in tags_raw.split(",") if tag.strip()]

    try:
        blog_base = BlogCreateSchemaBase(
            title=(form.get("title") or "").strip(),
            content=(form.get("content") or "").strip(),
            short_description=(form.get("short_description") or "").strip(),
            tags=tags,
        )
    except ValidationError as exc:
        errors = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in exc.errors()])
        user_role_id = user_data.role.id if user_data.role else None
        blog_obj = await BlogDAO.get_full_blog_info(
            session=session,
            blog_id=blog_id,
            author_id=user_data.id,
            user_role_id=user_role_id,
        )
        if isinstance(blog_obj, dict):
            return templates.TemplateResponse(
                request,
                "404.html",
                {"request": request, "blog_id": blog_id, "current_user": user_data},
                status_code=status.HTTP_404_NOT_FOUND,
            )
        blog = BlogFullResponse.model_validate(blog_obj).model_dump()
        context = {
            **_build_common_context(request, user_data),
            "blog": blog,
            "tags_str": tags_raw,
            "form_error": f"Ошибка валидации: {errors}",
        }
        return templates.TemplateResponse(
            request, "edit_blog.html", context, status_code=status.HTTP_400_BAD_REQUEST
        )

    user_role_id = user_data.role.id if user_data.role else None
    blog_obj = await BlogDAO.get_full_blog_info(
        session=session,
        blog_id=blog_id,
        author_id=user_data.id,
        user_role_id=user_role_id,
    )
    if isinstance(blog_obj, dict):
        return templates.TemplateResponse(
            request,
            "404.html",
            {"request": request, "blog_id": blog_id, "current_user": user_data},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    is_admin = user_data.role.id in [3, 4] if user_data.role else False
    if (blog_obj.author != user_data.id) and not is_admin:
        return templates.TemplateResponse(
            request,
            "404.html",
            {"request": request, "blog_id": blog_id, "current_user": user_data},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    blog_obj.title = blog_base.title
    blog_obj.content = blog_base.content
    blog_obj.short_description = blog_base.short_description

    tags_lower = [tag.lower() for tag in blog_base.tags]
    tags_ids: list[int] = []
    if tags_lower:
        tags_ids = await TagDAO.add_tags(session=session, tag_names=tags_lower)
        tags_entities = await TagDAO.find_by_ids(session=session, ids=tags_ids)
        blog_obj.tags.clear()
        for tag_entity in tags_entities:
            blog_obj.tags.append(tag_entity)
    else:
        blog_obj.tags.clear()

    try:
        await session.flush()
    except IntegrityError:
        # Откат транзакции и повторное чтение блога
        await session.rollback()
        blog_obj = await BlogDAO.get_full_blog_info(
            session=session,
            blog_id=blog_id,
            author_id=user_data.id,
            user_role_id=user_role_id,
        )
        if isinstance(blog_obj, dict):
            return templates.TemplateResponse(
                request,
                "404.html",
                {"request": request, "blog_id": blog_id, "current_user": user_data},
                status_code=status.HTTP_404_NOT_FOUND,
            )
        blog = BlogFullResponse.model_validate(blog_obj).model_dump()
        context = {
            **_build_common_context(request, user_data),
            "blog": blog,
            "tags_str": tags_raw,
            "form_error": "Блог с таким заголовком уже существует",
        }
        return templates.TemplateResponse(
            request, "edit_blog.html", context, status_code=status.HTTP_400_BAD_REQUEST
        )

    return RedirectResponse(
        url=f"/blogs/{blog_id}/", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/blogs/")
async def blogs_page(
    request: Request,
    author_id: int | None = None,
    tag: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 6,
    session: AsyncSession = SessionDep,
    user_data: User | None = Depends(get_current_user_optional),
):
    blogs = await BlogDAO.get_blog_list(
        session=session,
        author_id=author_id,
        tag=tag,
        search=search,
        page=page,
        page_size=page_size,
    )

    # Формируем сообщение о поиске
    search_message = None
    search_type = None
    if author_id:
        # Получаем имя автора
        author = await UsersDAO.find_one_or_none_by_id(
            data_id=author_id, session=session
        )
        if author:
            author_name = f"{author.first_name} {author.last_name}"
            search_message = f"Автор: {author_name} (ID: {author_id})"
            search_type = "author"
        else:
            search_message = f"Автор с ID {author_id} не найден"
            search_type = "author_not_found"
    elif tag:
        search_message = f"Тег: {tag}"
        search_type = "tag"
        if blogs.get("total_result", 0) == 0:
            search_message = f"Тег '{tag}' не найден"
            search_type = "tag_not_found"
    elif search:
        search_message = f"Поиск: {search}"
        search_type = "search"
        if blogs.get("total_result", 0) == 0:
            search_message = f"По запросу '{search}' ничего не найдено"
            search_type = "search_not_found"

    context = {
        **_build_common_context(request, user_data),
        "article": blogs,
        "filters": {"author_id": author_id, "tag": tag, "search": search},
        "search_message": search_message,
        "search_type": search_type,
    }
    return templates.TemplateResponse(request, "posts.html", context)


def _read_likes() -> list[dict]:
    """Чтение лайков из JSON файла."""
    import json
    from pathlib import Path

    likes_file = Path("data/likes.json")
    try:
        if not likes_file.exists():
            return []
        with open(likes_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


@router.get("/blogs/liked/")
async def liked_blogs_page(
    request: Request,
    page: int = 1,
    page_size: int = 6,
    session: AsyncSession = SessionDep,
    user_data: User | None = Depends(get_current_user_optional),
):
    if not user_data:
        return RedirectResponse(
            url="/auth/?mode=login", status_code=status.HTTP_302_FOUND
        )

    # Получаем ID постов, которые лайкнул текущий пользователь из likes.json
    all_likes = _read_likes()
    liked_post_ids = [
        like["post_id"]
        for like in all_likes
        if like.get("user_id") == user_data.id and like.get("liked", False)
    ]

    # Получаем пагинированный список понравившихся блогов из базы данных
    liked_blogs = await BlogDAO.get_liked_blogs(
        session=session, post_ids=liked_post_ids, page=page, page_size=page_size
    )

    context = {
        **_build_common_context(request, user_data),
        "article": liked_blogs,
        "filters": {},
    }
    return templates.TemplateResponse(request, "liked_posts.html", context)


@router.get("/blogs/drafts/")
async def drafts_page(
    request: Request,
    page: int = 1,
    page_size: int = 10,
    session: AsyncSession = SessionDep,
    user_data: User = Depends(get_current_user),
):
    drafts = await BlogDAO.get_draft_blogs(
        session=session, author_id=user_data.id, page=page, page_size=page_size
    )
    context = {
        **_build_common_context(request, user_data),
        "article": drafts,
        "filters": {},
    }
    return templates.TemplateResponse(request, "drafts.html", context)


@router.get("/blogs/all-drafts/")
async def all_drafts_page(
    request: Request,
    page: int = 1,
    page_size: int = 10,
    session: AsyncSession = SessionDep,
    user_data: User = Depends(get_current_user),
):
    # Проверяем, является ли пользователь админом или суперадмином
    if not user_data.role or user_data.role.name not in ["Admin", "SuperAdmin"]:
        return templates.TemplateResponse(
            request,
            "404.html",
            {"request": request, "current_user": user_data},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    drafts = await BlogDAO.get_draft_blogs(
        session=session,
        author_id=None,  # Получаем все черновики, не только для конкретного автора
        page=page,
        page_size=page_size,
    )
    context = {
        **_build_common_context(request, user_data),
        "article": drafts,
        "filters": {},
    }
    return templates.TemplateResponse(request, "drafts.html", context)


@router.get("/blogs/{blog_id}/")
async def blog_details(
    request: Request,
    blog_id: int,
    blog_info: BlogFullResponse | BlogNotFind = Depends(get_blog_info),
    user_data: User | None = Depends(get_current_user_optional),
):
    # get_blog_info возвращает BlogNotFind или BlogFullResponse
    from app.api.schemas import BlogNotFind

    if isinstance(blog_info, BlogNotFind) or isinstance(blog_info, dict):
        return templates.TemplateResponse(
            request,
            "404.html",
            {"request": request, "blog_id": blog_id, "current_user": user_data},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    blog = BlogFullResponse.model_validate(blog_info).model_dump()
    blog["content"] = markdown2.markdown(
        blog["content"], extras=["fenced-code-blocks", "tables", "code-friendly"]
    )
    # Проверяем, является ли пользователь админом или суперадмином
    is_admin = False
    if user_data and user_data.role:
        is_admin = user_data.role.id in [3, 4]  # 3 = Admin, 4 = SuperAdmin
    context = {
        **_build_common_context(request, user_data),
        "article": blog,
        "current_user_id": user_data.id if user_data else None,
        "is_admin": is_admin,
    }
    return templates.TemplateResponse(request, "post.html", context)


@router.get("/auth/")
async def auth_page(
    request: Request,
    mode: str = "login",
    message: str | None = None,
    user_data: User | None = Depends(get_current_user_optional),
    session: AsyncSession = SessionDep,
):
    # Получаем список всех ролей для выпадающего списка
    roles = await RoleDAO.find_all(session=session, filters=None)
    context = {
        **_build_common_context(request, user_data),
        "mode": mode,
        "form_error": None,
        "form_success": message,
        "roles": roles,
    }
    return templates.TemplateResponse(request, "auth.html", context)


@router.post("/auth/register/form")
async def register_user_view(
    request: Request,
    session: AsyncSession = TransactionSessionDep,
):
    form = await request.form()
    mode = "register"
    form_dict = dict(form)
    try:
        user_data = SUserRegister(**form_dict)
    except ValidationError as exc:
        errors = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in exc.errors()])
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JSONResponse(
                {"ok": False, "error": errors}, status_code=status.HTTP_400_BAD_REQUEST
            )
        # Получаем список ролей для контекста
        roles = await RoleDAO.find_all(session=session, filters=None)
        context = {
            **_build_common_context(request, None),
            "mode": mode,
            "form_error": f"Ошибка валидации: {errors}",
            "form_success": None,
            "roles": roles,
        }
        return templates.TemplateResponse(
            request, "auth.html", context, status_code=status.HTTP_400_BAD_REQUEST
        )

    existing_user = await UsersDAO.find_one_or_none(
        session=session, filters=EmailModel(email=user_data.email)
    )
    if existing_user:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JSONResponse(
                {"ok": False, "error": "Пользователь с таким email уже существует"},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        # Получаем список ролей для контекста
        roles = await RoleDAO.find_all(session=session, filters=None)
        context = {
            **_build_common_context(request, None),
            "mode": mode,
            "form_error": "Пользователь с таким email уже существует",
            "form_success": None,
            "roles": roles,
        }
        return templates.TemplateResponse(
            request, "auth.html", context, status_code=status.HTTP_400_BAD_REQUEST
        )

    existing_phone = await UsersDAO.find_one_or_none(
        session=session, filters=PhoneModel(phone_number=user_data.phone_number)
    )
    if existing_phone:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JSONResponse(
                {"ok": False, "error": "Пользователь с таким телефоном уже существует"},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        roles = await RoleDAO.find_all(session=session, filters=None)
        context = {
            **_build_common_context(request, None),
            "mode": mode,
            "form_error": "Пользователь с таким телефоном уже существует",
            "form_success": None,
            "roles": roles,
        }
        return templates.TemplateResponse(
            request, "auth.html", context, status_code=status.HTTP_400_BAD_REQUEST
        )

    user_data_dict = user_data.model_dump()
    user_data_dict.pop("confirm_password", None)
    try:
        await UsersDAO.add(session=session, values=SUserAddDB(**user_data_dict))
    except IntegrityError:
        # Подстраховка на случай гонки: возвращаем ту же ошибку без 500
        roles = await RoleDAO.find_all(session=session, filters=None)
        context = {
            **_build_common_context(request, None),
            "mode": mode,
            "form_error": "Пользователь с таким email или телефоном уже существует",
            "form_success": None,
            "roles": roles,
        }
        return templates.TemplateResponse(
            request, "auth.html", context, status_code=status.HTTP_400_BAD_REQUEST
        )
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JSONResponse(
            {"ok": True, "message": "Регистрация успешна"},
            status_code=status.HTTP_201_CREATED,
        )
    redirect = RedirectResponse(
        url="/auth/?mode=login&message=Регистрация%20успешна",
        status_code=status.HTTP_303_SEE_OTHER,
    )
    return redirect


@router.post("/auth/login/form")
async def login_user_view(
    request: Request,
    session: AsyncSession = SessionDep,
):
    form = await request.form()
    form_dict = dict(form)
    email = form_dict.get("email") or ""
    password = form_dict.get("password") or ""
    try:
        user = await authenticate_user(email=email, password=password, session=session)
        if not user:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JSONResponse(
                    {"ok": False, "error": "Неверный email или пароль"},
                    status_code=status.HTTP_401_UNAUTHORIZED,
                )
            context = {
                **_build_common_context(request, None),
                "mode": "login",
                "form_error": "Неверный email или пароль",
                "form_success": None,
            }
            return templates.TemplateResponse(
                request, "auth.html", context, status_code=status.HTTP_401_UNAUTHORIZED
            )
    except Exception:
        # Любая непредвиденная ошибка авторизации — показываем безопасное сообщение
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JSONResponse(
                {"ok": False, "error": "Сервис недоступен, попробуйте позже"},
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        context = {
            **_build_common_context(request, None),
            "mode": "login",
            "form_error": "Сервис недоступен, попробуйте позже",
            "form_success": None,
        }
        return templates.TemplateResponse(
            request,
            "auth.html",
            context,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    access_token = create_access_token({"sub": str(user.id)})
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        response = JSONResponse({"ok": True, "message": "Авторизация успешна"})
        response.set_cookie(
            key="users_access_token", value=access_token, httponly=False
        )
        return response
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="users_access_token", value=access_token, httponly=False)
    return response


@router.get("/profile/")
async def profile_page(
    request: Request,
    user_data: User = Depends(get_current_user),
    session: AsyncSession = SessionDep,
):
    # Получаем список всех ролей для выпадающего списка
    roles = await RoleDAO.find_all(session=session, filters=None)
    context = {
        **_build_common_context(request, user_data),
        "form_error": None,
        "form_success": None,
        "roles": roles,
    }
    return templates.TemplateResponse(request, "profile.html", context)


@router.post("/profile/")
async def profile_update(
    request: Request,
    user_data: User = Depends(get_current_user),
    session: AsyncSession = TransactionSessionDep,
):
    form = await request.form()
    form_dict = dict(form)

    # Преобразуем role_id в int, если он есть
    if "role_id" in form_dict and form_dict["role_id"]:
        try:
            form_dict["role_id"] = int(form_dict["role_id"])
        except (ValueError, TypeError):
            form_dict.pop("role_id", None)  # Удаляем невалидный role_id

    # Фильтрация пустых строковых значений
    filtered_dict = {}
    for k, v in form_dict.items():
        if isinstance(v, str):
            if v.strip():
                filtered_dict[k] = v.strip()
        elif v is not None:
            filtered_dict[k] = v
    form_dict = filtered_dict

    try:
        update_data = SUserUpdate(**form_dict)
    except ValidationError as exc:
        errors = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in exc.errors()])
        # Получаем список ролей для контекста
        roles = await RoleDAO.find_all(session=session, filters=None)
        context = {
            **_build_common_context(request, user_data),
            "form_error": f"Ошибка валидации: {errors}",
            "form_success": None,
            "roles": roles,
        }
        return templates.TemplateResponse(
            request, "profile.html", context, status_code=status.HTTP_400_BAD_REQUEST
        )

    update_dict = update_data.model_dump(exclude_unset=True, exclude_none=True)
    update_dict.pop("confirm_password", None)

    if not update_dict:
        # Получаем список ролей для контекста
        roles = await RoleDAO.find_all(session=session, filters=None)
        context = {
            **_build_common_context(request, user_data),
            "form_error": None,
            "form_success": "Нет изменений для сохранения",
            "roles": roles,
        }
        return templates.TemplateResponse(request, "profile.html", context)

    if "email" in update_dict:
        existing_user = await UsersDAO.find_one_or_none(
            session=session, filters=EmailModel(email=update_dict["email"])
        )
        if existing_user and existing_user.id != user_data.id:
            # Получаем список ролей для контекста
            roles = await RoleDAO.find_all(session=session, filters=None)
            context = {
                **_build_common_context(request, user_data),
                "form_error": "Пользователь с таким email уже существует",
                "form_success": None,
                "roles": roles,
            }
            return templates.TemplateResponse(
                request,
                "profile.html",
                context,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    if "phone_number" in update_dict:
        existing_phone = await UsersDAO.find_one_or_none(
            session=session,
            filters=PhoneModel(phone_number=update_dict["phone_number"]),
        )
        if existing_phone and existing_phone.id != user_data.id:
            roles = await RoleDAO.find_all(session=session, filters=None)
            context = {
                **_build_common_context(request, user_data),
                "form_error": "Пользователь с таким телефоном уже существует",
                "form_success": None,
                "roles": roles,
            }
            return templates.TemplateResponse(
                request,
                "profile.html",
                context,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    # Перезагружаем пользователя из текущей сессии по ID
    current_user = await UsersDAO.find_one_or_none_by_id(
        data_id=user_data.id, session=session
    )
    if not current_user:
        # Получаем список ролей для контекста
        roles = await RoleDAO.find_all(session=session, filters=None)
        context = {
            **_build_common_context(request, user_data),
            "form_error": "Пользователь не найден",
            "form_success": None,
            "roles": roles,
        }
        return templates.TemplateResponse(
            request, "profile.html", context, status_code=status.HTTP_404_NOT_FOUND
        )

    # Обновляем поля
    for key, value in update_dict.items():
        setattr(current_user, key, value)

    # Сохраняем изменения в базу данных
    await session.flush()

    # Обновление связи с ролью после изменения role_id
    await session.refresh(current_user)

    # Обновляем user_data для контекста
    user_data = current_user

    # Получаем список ролей для контекста
    roles = await RoleDAO.find_all(session=session, filters=None)
    context = {
        **_build_common_context(request, user_data),
        "form_error": None,
        "form_success": "Профиль успешно обновлен",
        "roles": roles,
    }
    return templates.TemplateResponse(request, "profile.html", context)
