from contextlib import asynccontextmanager
from functools import wraps
from typing import AsyncGenerator, Callable, Optional

from fastapi import Depends
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dao.database import async_session_maker


class DatabaseSessionManager:
    """Управление асинхронными сессиями БД и транзакциями."""

    def __init__(self, session_maker: async_sessionmaker[AsyncSession]):
        self.session_maker = session_maker

    @asynccontextmanager
    async def create_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Создание и предоставление новой сессии БД."""
        async with self.session_maker() as session:
            try:
                yield session
            except Exception as e:
                logger.error(f"Ошибка при создании сессии базы данных: {e}")
                raise
            finally:
                await session.close()

    @asynccontextmanager
    async def transaction(self, session: AsyncSession) -> AsyncGenerator[None, None]:
        """
        Управление транзакцией: коммит при успехе, откат при ошибке.
        """
        try:
            yield
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.exception(f"Ошибка транзакции: {e}")
            raise

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Зависимость FastAPI для сессии без транзакции."""
        async with self.create_session() as session:
            yield session

    async def get_transaction_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Зависимость FastAPI для сессии с транзакцией."""
        async with self.create_session() as session:
            async with self.transaction(session):
                yield session

    def connection(self, isolation_level: Optional[str] = None, commit: bool = True):
        """Декоратор для управления сессией с настройкой изоляции и коммита."""

        def decorator(method):
            @wraps(method)
            async def wrapper(*args, **kwargs):
                async with self.session_maker() as session:
                    try:
                        if isolation_level:
                            await session.execute(
                                text(
                                    f"SET TRANSACTION ISOLATION LEVEL {isolation_level}"
                                )
                            )

                        result = await method(*args, session=session, **kwargs)

                        if commit:
                            await session.commit()

                        return result
                    except Exception as e:
                        await session.rollback()
                        logger.error(f"Ошибка при выполнении транзакции: {e}")
                        raise
                    finally:
                        await session.close()

            return wrapper

        return decorator

    @property
    def session_dependency(self) -> Callable:
        """Зависимость FastAPI для сессии без транзакции."""
        return Depends(self.get_session)

    @property
    def transaction_session_dependency(self) -> Callable:
        """Зависимость FastAPI с транзакциями."""
        return Depends(self.get_transaction_session)


# Инициализация менеджера сессий базы данных
session_manager = DatabaseSessionManager(async_session_maker)

# Зависимости FastAPI для использования сессий
SessionDep = session_manager.session_dependency
TransactionSessionDep = session_manager.transaction_session_dependency
