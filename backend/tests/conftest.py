"""
Pytest configuration and shared fixtures.
Test database: SQLite (in-memory).
"""
import pytest_asyncio
from uuid import uuid4
from datetime import datetime, timezone
from decimal import Decimal
from httpx import AsyncClient, ASGITransport

from sqlalchemy import event, text, String, JSON
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.transaction import Transaction
from app.core.security import get_password_hash, create_access_token



# Patch PostgreSQL-specific types so SQLite can handle them


@event.listens_for(Base.metadata, "before_create")
def patch_types_for_sqlite(target, connection, **kw):
    """Replace UUID->String(36) and JSONB->JSON when running on SQLite."""
    if connection.dialect.name != "sqlite":
        return
    for table in target.tables.values():
        for col in table.columns:
            if isinstance(col.type, PG_UUID):
                col.type = String(36)
            elif isinstance(col.type, JSONB):
                col.type = JSON()



# Test database - SQLite in-memory, single shared connection


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)



# Session-scoped: create tables once, drop after all tests


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    """Create all tables once before the test session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)



# Function-scoped: clean tables after every test


async def _clear_all_tables():
    """Delete every row from every table in dependency-safe order."""
    async with TestSessionLocal() as session:
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(text(f"DELETE FROM {table.name}"))
        await session.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_db():
    """Auto-used: wipe tables after each test."""
    yield
    await _clear_all_tables()



# DB session and HTTP client


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Fresh AsyncSession for each test."""
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    """AsyncClient wired to the FastAPI app via test DB."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()



# User fixtures


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """A standard active user committed to the test DB."""
    user = User(
        id=uuid4(),
        email="testuser@example.com",
        username="testuser",
        password_hash=get_password_hash("Password123"),
        role=UserRole.USER,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """An admin user committed to the test DB."""
    user = User(
        id=uuid4(),
        email="admin@example.com",
        username="adminuser",
        password_hash=get_password_hash("AdminPass123"),
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
def auth_headers(test_user: User) -> dict:
    """Bearer token headers for test_user."""
    token = create_access_token(data={"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
def admin_headers(admin_user: User) -> dict:
    """Bearer token headers for admin_user."""
    token = create_access_token(data={"sub": str(admin_user.id)})
    return {"Authorization": f"Bearer {token}"}



# Transaction helpers


def make_transaction_payload(overrides: dict = None) -> dict:
    """Build a valid transaction payload. Each call gets a unique transaction_id."""
    payload = {
        "transaction_id": f"txn_{uuid4().hex[:12]}",
        "amount": "150.00",
        "currency": "USD",
        "transaction_type": "PAYMENT",
        "customer_id": str(uuid4()),
        "payment_method": "CARD",
        "transaction_time": datetime.now(timezone.utc).isoformat(),
    }
    if overrides:
        payload.update(overrides)
    return payload


@pytest_asyncio.fixture
async def existing_transaction(db_session: AsyncSession, test_user: User) -> Transaction:
    """A Transaction already saved in the test DB."""
    txn = Transaction(
        id=uuid4(),
        transaction_id=f"txn_existing_{uuid4().hex[:8]}",
        amount=Decimal("200.00"),
        currency="USD",
        transaction_type="PAYMENT",
        customer_id=uuid4(),
        payment_method="CARD",
        transaction_time=datetime.now(timezone.utc),
        status="pending",
        is_fraud=False,
    )
    db_session.add(txn)
    await db_session.commit()
    await db_session.refresh(txn)
    return txn