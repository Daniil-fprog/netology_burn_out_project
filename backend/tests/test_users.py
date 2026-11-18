"""Тесты для роута users (register, me, get_users, get_user_by_id)."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.db.database import get_db, Base
from app.main import app
from app.models.user import UserModel


# === Настройка тестовой БД ===
SQLALCHEMY_DATABASE_URL = "sqlite:///./db_store/test_users.db"

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


@pytest.fixture
def test_user_data():
    """Данные для создания тестового пользователя."""
    return {
        "name": "Тестовый Пользователь",
        "login": "testuser",
        "password": "securepassword123",
        "phone": "+79991234567",
    }


@pytest.fixture
def auth_headers(client, test_user_data):
    """Создает пользователя и возвращает заголовки авторизации."""
    hashed_password = hash_password(test_user_data["password"])
    user = UserModel(
        name=test_user_data["name"],
        login=test_user_data["login"],
        password_hash=hashed_password,
        phone=test_user_data["phone"],
    )
    
    db = TestingSessionLocal()
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    
    login_data = {
        "login": test_user_data["login"],
        "password": test_user_data["password"],
    }
    response = client.post("/api/v1/users/login", json=login_data)
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestRegister:
    """Тесты эндпоинта POST /api/v1/users/register."""

    def test_register_success(self, client):
        """Успешная регистрация пользователя."""
        register_data = {
            "name": "Новый Пользователь",
            "login": "newuser",
            "password": "newpassword123",
            "phone": "+79997778899",
        }
        response = client.post("/api/v1/users/register", json=register_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Новый Пользователь"
        assert data["login"] == "newuser"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_register_missing_fields(self, client):
        """Регистрация с отсутствующими полями."""
        register_data = {
            "name": "Только Имя",
        }
        response = client.post("/api/v1/users/register", json=register_data)
        
        assert response.status_code == 422

    def test_register_empty_body(self, client):
        """Регистрация с пустым телом."""
        response = client.post("/api/v1/users/register", json={})
        
        assert response.status_code == 422

    def test_register_existing_login(self, client, test_user_data):
        """Регистрация с уже существующим логином."""
        hashed_password = hash_password(test_user_data["password"])
        user = UserModel(
            name=test_user_data["name"],
            login=test_user_data["login"],
            password_hash=hashed_password,
        )
        
        db = TestingSessionLocal()
        db.add(user)
        db.commit()
        db.close()

        register_data = {
            "name": "Другой Пользователь",
            "login": test_user_data["login"],
            "password": "anotherpassword",
        }
        response = client.post("/api/v1/users/register", json=register_data)
        
        assert response.status_code == 400

    def test_register_duplicate_login_different_case(self, client):
        """Регистрация с логином в другом регистре (если не реализовано uniqueness)."""
        hashed_password = hash_password("pass123")
        user = UserModel(
            name="Old User",
            login="uniqueuser",
            password_hash=hashed_password,
        )
        
        db = TestingSessionLocal()
        db.add(user)
        db.commit()
        db.close()

        register_data = {
            "name": "New User",
            "login": "uniqueuser",
            "password": "newpass123",
        }
        response = client.post("/api/v1/users/register", json=register_data)
        
        assert response.status_code in [400, 422]


class TestGetMe:
    """Тесты эндпоинта GET /api/v1/users/me."""

    def test_get_me_success(self, client, auth_headers):
        """Успешное получение данных о себе."""
        response = client.get("/api/v1/users/me", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["login"] == "testuser"
        assert "id" in data

    def test_get_me_unauthorized(self, client):
        """Получение данных о себе без авторизации."""
        response = client.get("/api/v1/users/me")
        
        assert response.status_code == 401

    def test_get_me_invalid_token(self, client):
        """Получение данных с неверным токеном."""
        headers = {"Authorization": "Bearer invalidtoken"}
        response = client.get("/api/v1/users/me", headers=headers)
        
        assert response.status_code == 401


class TestGetUsers:
    """Тесты эндпоинта GET /api/v1/users/."""

    def test_get_users_success(self, client, auth_headers):
        """Успешное получение списка пользователей."""
        response = client.get("/api/v1/users/", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_users_unauthorized(self, client):
        """Получение списка пользователей без авторизации."""
        response = client.get("/api/v1/users/")
        
        assert response.status_code == 401


class TestGetUserById:
    """Тесты эндпоинта GET /api/v1/users/{userId}."""

    def test_get_user_by_id_success(self, client, auth_headers):
        """Успешное получение пользователя по ID."""
        user = UserModel(
            name="Другой Пользователь",
            login="otheruser",
            password_hash=hash_password("otherpass"),
        )
        db = TestingSessionLocal()
        db.add(user)
        db.commit()
        db.refresh(user)
        db.close()

        response = client.get(f"/api/v1/users/{user.id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_get_user_by_id_not_found(self, client, auth_headers):
        """Получение несуществующего пользователя по ID."""
        response = client.get("/api/v1/users/999999", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_get_user_by_id_unauthorized(self, client):
        """Получение пользователя без авторизации."""
        response = client.get("/api/v1/users/1")

        assert response.status_code == 401
