"""Тесты для роута auth (login)."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_current_user, hash_password
from app.db.database import get_db, Base, engine
from app.main import app
from app.models.user import UserModel


# === Настройка тестовой БД ===
SQLALCHEMY_DATABASE_URL = "sqlite:///./db_store/test_auth.db"

test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


@pytest.fixture(scope="function")
def client():
    """Создает тестовый клиент с новой БД для каждого теста."""
    Base.metadata.create_all(bind=test_engine)
    
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


class TestLogin:
    """Тесты эндпоинта POST /api/v1/users/login."""

    def test_login_success(self, client):
        """Успешный вход пользователя."""
        hashed_password = hash_password("testpass123")
        user = UserModel(
            name="Тестовый Пользователь",
            login="testuser",
            password_hash=hashed_password,
        )
        
        db = TestingSessionLocal()
        db.add(user)
        db.commit()
        db.refresh(user)
        db.close()

        login_data = {
            "login": "testuser",
            "password": "testpass123",
        }
        response = client.post("/api/v1/users/login", json=login_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_credentials(self, client):
        """Вход с неверными credentials."""
        login_data = {
            "login": "nonexistent",
            "password": "wrongpassword",
        }
        response = client.post("/api/v1/users/login", json=login_data)
        
        assert response.status_code == 401
        assert response.json()["detail"] == "Неверный логин или пароль"

    def test_login_empty_body(self, client):
        """Вход с пустым телом запроса."""
        response = client.post("/api/v1/users/login", json={})
        
        assert response.status_code == 422

    def test_login_missing_login(self, client):
        """Вход без логина."""
        login_data = {
            "password": "somepassword",
        }
        response = client.post("/api/v1/users/login", json=login_data)
        
        assert response.status_code == 422

    def test_login_missing_password(self, client):
        """Вход без пароля."""
        login_data = {
            "login": "someuser",
        }
        response = client.post("/api/v1/users/login", json=login_data)
        
        assert response.status_code == 422

    def test_login_empty_password(self, client):
        """Вход с пустым паролем - возвращает 422 из-за валидации."""
        hashed_password = hash_password("")
        user = UserModel(
            name="Тестовый",
            login="emptyuser",
            password_hash=hashed_password,
        )

        db = TestingSessionLocal()
        db.add(user)
        db.commit()
        db.close()

        login_data = {
            "login": "emptyuser",
            "password": "",
        }
        response = client.post("/api/v1/users/login", json=login_data)

        # Pydantic возвращает 422 при валидации пустого пароля
        assert response.status_code == 422

    def test_login_whitespace_password(self, client):
        """Вход с пробелами в пароле."""
        login_data = {
            "login": "testuser",
            "password": "   ",
        }
        response = client.post("/api/v1/users/login", json=login_data)
        
        assert response.status_code == 401


def test_get_current_user_rejects_inactive_user(client):
    db = TestingSessionLocal()
    try:
        user = UserModel(
            name="Деактивированный пользователь",
            login="inactive-user",
            password_hash=hash_password("testpass123"),
            is_active=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_access_token({"sub": str(user.id)})

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(token=token, db=db)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Пользователь не авторизован"
    finally:
        db.close()
