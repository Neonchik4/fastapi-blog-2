import os
import re
import sys
from pathlib import Path
from typing import AsyncGenerator, Callable, Generator

import pytest
from httpx import ASGITransport, AsyncClient
from loguru import logger as loguru_logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Гарантируем, что корень проекта в sys.path (pytest в некоторых режимах импорта может его не добавить).
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _ensure_test_env() -> None:
    # `app.config.Settings` требует эти переменные. Для тестов достаточно безопасных дефолтов.
    os.environ.setdefault("SECRET_KEY", "test-secret-key")
    os.environ.setdefault("ALGORITHM", "HS256")


def _safe_filename(name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", name)
    return name[:150] or "test"


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    root = Path(__file__).resolve().parents[1]
    p = root / "test_data"
    p.mkdir(parents=True, exist_ok=True)
    (p / "logs").mkdir(parents=True, exist_ok=True)
    return p


@pytest.fixture(autouse=True)
def test_log(
    request: pytest.FixtureRequest, test_data_dir: Path
) -> Generator[Callable[[str], None], None, None]:
    """
    Логирование в `test_data/logs`:
    - любая запись через loguru в коде проекта тоже попадёт сюда (sink на время теста)
    - тест может явно логировать через возвращаемую функцию `log(msg)`
    """
    log_path = test_data_dir / "logs" / f"{_safe_filename(request.node.nodeid)}.log"
    sink_id = loguru_logger.add(
        str(log_path), level="DEBUG", enqueue=False, backtrace=True, diagnose=False
    )

    def _log(msg: str) -> None:
        loguru_logger.info(msg)

    yield _log

    loguru_logger.remove(sink_id)


@pytest.fixture(scope="session")
def _db_url(test_data_dir: Path) -> str:
    db_path = test_data_dir / "test_db.sqlite3"
    if db_path.exists():
        db_path.unlink()
    return f"sqlite+aiosqlite:///{db_path.as_posix()}"


@pytest.fixture(scope="session")
async def db_engine(_db_url: str) -> AsyncGenerator[AsyncEngine, None]:
    _ensure_test_env()
    engine = create_async_engine(_db_url)

    # Импортируем модели ДО create_all, чтобы они зарегистрировались в metadata.
    from app.api import models as _api_models  # noqa: F401
    from app.auth import models as _auth_models  # noqa: F401
    from app.dao.database import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Сидим роли с фиксированными id (важно для проверок id in [3,4])
    from app.auth.models import Role

    SessionLocal = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with SessionLocal() as session:
        session.add_all(
            [
                Role(id=1, name="User"),
                Role(id=2, name="Moderator"),
                Role(id=3, name="Admin"),
                Role(id=4, name="SuperAdmin"),
            ]
        )
        await session.commit()

    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
def db_sessionmaker(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def app(db_sessionmaker: async_sessionmaker[AsyncSession]):
    _ensure_test_env()
    from app.dao.session_maker import session_manager
    from app.main import app as fastapi_app

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with db_sessionmaker() as session:
            yield session

    async def override_get_transaction_session() -> AsyncGenerator[AsyncSession, None]:
        async with db_sessionmaker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    fastapi_app.dependency_overrides[session_manager.get_session] = override_get_session
    fastapi_app.dependency_overrides[session_manager.get_transaction_session] = (
        override_get_transaction_session
    )

    return fastapi_app


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    # httpx.AsyncClient автоматически сохраняет cookies между запросами
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False
    ) as ac:
        yield ac


@pytest.fixture
def likes_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    likes_path = tmp_path / "likes.json"
    likes_path.write_text("[]", encoding="utf-8")
    import app.api.likes_router as likes_router

    monkeypatch.setattr(likes_router, "LIKES_FILE", likes_path)
    return likes_path


@pytest.fixture
async def ensure_user(db_sessionmaker: async_sessionmaker[AsyncSession]):
    """
    Идемпотентное создание пользователя:
    - если email уже есть, просто возвращаем его ORM-объект
    - если нет — создаём с известным паролем и возвращаем ORM-объект
    """
    from app.auth.dao import UsersDAO
    from app.auth.models import User
    from app.auth.schemas import EmailModel, SUserAddDB
    from app.auth.utils import get_password_hash

    async def _impl(
        email: str,
        *,
        password: str,
        phone: str,
        first_name: str = "Test",
        last_name: str = "User",
    ) -> User:
        async with db_sessionmaker() as session:
            existing = await UsersDAO.find_one_or_none(
                session=session, filters=EmailModel(email=email)
            )
            if existing:
                return existing

            hashed = get_password_hash(password)
            new_user = await UsersDAO.add(
                session=session,
                values=SUserAddDB(
                    email=email,
                    phone_number=phone,
                    first_name=first_name,
                    last_name=last_name,
                    password=hashed,
                ),
            )
            await session.commit()
            return new_user

    return _impl


@pytest.fixture(autouse=True)
async def _clean_test_db(db_sessionmaker: async_sessionmaker[AsyncSession]):
    """
    Изоляция тестов: БД в тестах session-scoped, поэтому данные "текут" между тестами
    и ломают ожидания (например, что список опубликованных пуст).
    Чистим основные таблицы перед каждым тестом, сохраняя `roles` (они сидятся один раз).
    """
    async with db_sessionmaker() as session:
        # порядок важен из-за FK
        await session.execute(text("DELETE FROM blog_tags"))
        await session.execute(text("DELETE FROM blogs"))
        await session.execute(text("DELETE FROM tags"))
        await session.execute(text("DELETE FROM users"))
        await session.commit()


@pytest.fixture
async def set_user_role(db_sessionmaker: async_sessionmaker[AsyncSession]):
    from sqlalchemy import select

    from app.auth.models import User

    async def _impl(user_id: int, role_id: int) -> None:
        async with db_sessionmaker() as session:
            user = (
                await session.execute(select(User).where(User.id == user_id))
            ).scalar_one()
            user.role_id = role_id
            await session.commit()

    return _impl
