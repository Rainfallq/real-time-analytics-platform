"""
Tests for authentication endpoints.

Coverage:
- POST /api/v1/auth/register
- POST /api/v1/auth/login
- POST /api/v1/auth/refresh
- GET  /api/v1/auth/me
- PUT  /api/v1/auth/me
- POST /api/v1/auth/change-password
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from tests.conftest import make_transaction_payload

pytestmark = pytest.mark.asyncio


# Register


class TestRegister:

    async def test_register_success(self, client: AsyncClient):
        response = await client.post("/api/v1/auth/register", json={
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "StrongPass123",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["username"] == "newuser"
        assert "password" not in data           # never expose password
        assert "password_hash" not in data

    async def test_register_duplicate_email(self, client: AsyncClient, test_user: User):
        response = await client.post("/api/v1/auth/register", json={
            "email": test_user.email,           # already exists
            "username": "otherusername",
            "password": "StrongPass123",
        })
        assert response.status_code == 400
        assert "email" in response.json()["detail"].lower()

    async def test_register_duplicate_username(self, client: AsyncClient, test_user: User):
        response = await client.post("/api/v1/auth/register", json={
            "email": "unique@example.com",
            "username": test_user.username,     # already exists
            "password": "StrongPass123",
        })
        assert response.status_code == 400
        assert "username" in response.json()["detail"].lower()

    async def test_register_weak_password(self, client: AsyncClient):
        """Password without digit should be rejected by validator."""
        response = await client.post("/api/v1/auth/register", json={
            "email": "weak@example.com",
            "username": "weakuser",
            "password": "nodigitshere",
        })
        assert response.status_code == 422

    async def test_register_invalid_email(self, client: AsyncClient):
        response = await client.post("/api/v1/auth/register", json={
            "email": "not-an-email",
            "username": "someuser",
            "password": "StrongPass123",
        })
        assert response.status_code == 422

    async def test_register_short_username(self, client: AsyncClient):
        response = await client.post("/api/v1/auth/register", json={
            "email": "short@example.com",
            "username": "ab",               # min_length=3
            "password": "StrongPass123",
        })
        assert response.status_code == 422



# Login


class TestLogin:

    async def test_login_with_email_success(self, client: AsyncClient, test_user: User):
        response = await client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "Password123",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_with_username_success(self, client: AsyncClient, test_user: User):
        response = await client.post("/api/v1/auth/login", json={
            "username": test_user.username,
            "password": "Password123",
        })
        assert response.status_code == 200
        assert "access_token" in response.json()

    async def test_login_wrong_password(self, client: AsyncClient, test_user: User):
        response = await client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "WrongPassword1",
        })
        assert response.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient):
        response = await client.post("/api/v1/auth/login", json={
            "email": "ghost@example.com",
            "password": "Password123",
        })
        assert response.status_code == 401

    async def test_login_no_identifier(self, client: AsyncClient):
        """Neither email nor username provided — should fail validation."""
        response = await client.post("/api/v1/auth/login", json={
            "password": "Password123",
        })
        assert response.status_code == 422

    async def test_login_inactive_user(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ):
        test_user.is_active = False
        await db_session.commit()

        response = await client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "Password123",
        })
        assert response.status_code == 403

        # restore for other tests
        test_user.is_active = True
        await db_session.commit()



# Token refresh


class TestRefresh:

    async def test_refresh_success(self, client: AsyncClient, test_user: User):
        # First login to get tokens
        login = await client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "Password123",
        })
        refresh_token = login.json()["refresh_token"]

        response = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_refresh_with_access_token_fails(
        self, client: AsyncClient, test_user: User
    ):
        """Access token must not be accepted as refresh token."""
        login = await client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "Password123",
        })
        access_token = login.json()["access_token"]

        response = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": access_token,  # wrong token type
        })
        assert response.status_code == 401

    async def test_refresh_invalid_token(self, client: AsyncClient):
        response = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": "this.is.garbage",
        })
        assert response.status_code == 401



# /me endpoints


class TestMe:

    async def test_get_me_success(
        self, client: AsyncClient, test_user: User, auth_headers: dict
    ):
        response = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["username"] == test_user.username

    async def test_get_me_unauthenticated(self, client: AsyncClient):
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    async def test_update_me_full_name(
        self, client: AsyncClient, auth_headers: dict
    ):
        response = await client.put(
            "/api/v1/auth/me",
            json={"full_name": "Updated Name"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["full_name"] == "Updated Name"

    async def test_update_me_unauthenticated(self, client: AsyncClient):
        response = await client.put("/api/v1/auth/me", json={"full_name": "Hacker"})
        assert response.status_code == 401



# Change password


class TestChangePassword:

    async def test_change_password_success(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_user: User
    ):
        response = await client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "Password123",
                "new_password": "NewPassword456",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200

        # Восстанавливаем пароль чтобы не ломать другие тесты
        await client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "NewPassword456",
                "new_password": "Password123",
            },
            headers=auth_headers,
        )

    async def test_change_password_wrong_current(
        self, client: AsyncClient, auth_headers: dict
    ):
        response = await client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "WrongPassword1",
                "new_password": "NewPassword456",
            },
            headers=auth_headers,
        )
        assert response.status_code == 400

    async def test_change_password_same_as_current(
        self, client: AsyncClient, auth_headers: dict
    ):
        response = await client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "Password123",
                "new_password": "Password123",   # same password
            },
            headers=auth_headers,
        )
        assert response.status_code == 400