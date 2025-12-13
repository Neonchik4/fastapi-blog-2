import pytest


class _FakeSession:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.closes = 0
        self.executed_sql: list[str] = []

    async def execute(self, stmt):
        # `stmt` может быть sqlalchemy.text(...)
        self.executed_sql.append(str(stmt))
        return None

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def close(self):
        self.closes += 1


class _FakeSessionCtx:
    def __init__(self, session: _FakeSession):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        # В реальной SQLAlchemy сессия закрывается тут; в коде менеджера есть свой finally close().
        return False


def _fake_sessionmaker(session: _FakeSession):
    def _maker():
        return _FakeSessionCtx(session)

    return _maker


@pytest.mark.asyncio
async def test_create_session_yields_and_closes_on_success():
    """Функция: DatabaseSessionManager.create_session"""
    from app.dao.session_maker import DatabaseSessionManager

    s = _FakeSession()
    mgr = DatabaseSessionManager(_fake_sessionmaker(s))

    async with mgr.create_session() as session:
        assert session is s
        assert s.closes == 0

    assert s.closes == 1


@pytest.mark.asyncio
async def test_create_session_closes_and_reraises_on_error():
    """Функция: DatabaseSessionManager.create_session (ветка except + finally)"""
    from app.dao.session_maker import DatabaseSessionManager

    s = _FakeSession()
    mgr = DatabaseSessionManager(_fake_sessionmaker(s))

    with pytest.raises(RuntimeError):
        async with mgr.create_session():
            raise RuntimeError("boom")

    assert s.closes == 1


@pytest.mark.asyncio
async def test_transaction_commits_on_success_and_rolls_back_on_error():
    """Функция: DatabaseSessionManager.transaction"""
    from app.dao.session_maker import DatabaseSessionManager

    s1 = _FakeSession()
    mgr = DatabaseSessionManager(_fake_sessionmaker(s1))

    async with mgr.transaction(s1):
        pass
    assert s1.commits == 1
    assert s1.rollbacks == 0

    s2 = _FakeSession()
    mgr2 = DatabaseSessionManager(_fake_sessionmaker(s2))
    with pytest.raises(ValueError):
        async with mgr2.transaction(s2):
            raise ValueError("fail")
    assert s2.commits == 0
    assert s2.rollbacks == 1


@pytest.mark.asyncio
async def test_get_session_and_get_transaction_session_yield_session():
    """Функции: DatabaseSessionManager.get_session / get_transaction_session"""
    from app.dao.session_maker import DatabaseSessionManager

    s = _FakeSession()
    mgr = DatabaseSessionManager(_fake_sessionmaker(s))

    agen = mgr.get_session()
    got = await agen.__anext__()
    assert got is s
    with pytest.raises(StopAsyncIteration):
        await agen.__anext__()
    assert s.closes == 1

    s2 = _FakeSession()
    mgr2 = DatabaseSessionManager(_fake_sessionmaker(s2))
    agen2 = mgr2.get_transaction_session()
    got2 = await agen2.__anext__()
    assert got2 is s2
    with pytest.raises(StopAsyncIteration):
        await agen2.__anext__()
    assert s2.commits == 1
    assert s2.rollbacks == 0
    assert s2.closes == 1


@pytest.mark.asyncio
async def test_connection_decorator_sets_isolation_and_commits_by_default():
    """Функция: DatabaseSessionManager.connection (commit=True, isolation_level задан)"""
    from app.dao.session_maker import DatabaseSessionManager

    s = _FakeSession()
    mgr = DatabaseSessionManager(_fake_sessionmaker(s))

    @mgr.connection(isolation_level="SERIALIZABLE", commit=True)
    async def do_work(*, session):
        return "ok"

    assert await do_work() == "ok"
    assert any(
        "SET TRANSACTION ISOLATION LEVEL SERIALIZABLE" in sql for sql in s.executed_sql
    )
    assert s.commits == 1
    assert s.rollbacks == 0
    assert s.closes == 1


@pytest.mark.asyncio
async def test_connection_decorator_commit_false_does_not_commit():
    """Функция: DatabaseSessionManager.connection (commit=False)"""
    from app.dao.session_maker import DatabaseSessionManager

    s = _FakeSession()
    mgr = DatabaseSessionManager(_fake_sessionmaker(s))

    @mgr.connection(commit=False)
    async def do_work(*, session):
        return 123

    assert await do_work() == 123
    assert s.commits == 0
    assert s.rollbacks == 0
    assert s.closes == 1


@pytest.mark.asyncio
async def test_connection_decorator_rolls_back_on_exception():
    """Функция: DatabaseSessionManager.connection (ветка except => rollback)"""
    from app.dao.session_maker import DatabaseSessionManager

    s = _FakeSession()
    mgr = DatabaseSessionManager(_fake_sessionmaker(s))

    @mgr.connection(commit=True)
    async def do_work(*, session):
        raise RuntimeError("kaboom")

    with pytest.raises(RuntimeError):
        await do_work()
    assert s.commits == 0
    assert s.rollbacks == 1
    assert s.closes == 1


def test_fastapi_dependencies_are_depends_objects():
    """Свойства: session_dependency / transaction_session_dependency (+ алиасы SessionDep/TransactionSessionDep)"""
    from fastapi.params import Depends as DependsParam

    from app.dao import session_maker as sm

    assert isinstance(sm.session_manager.session_dependency, DependsParam)
    assert isinstance(sm.session_manager.transaction_session_dependency, DependsParam)
    assert isinstance(sm.SessionDep, DependsParam)
    assert isinstance(sm.TransactionSessionDep, DependsParam)
