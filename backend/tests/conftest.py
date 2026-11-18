"""Конфигурация pytest для API тестов."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import hash_password
from app.db.database import Base, get_db
from app.main import app
from app.models.user import UserModel
from app.services.user_service import register_user_service
from app.schemas.user import UserCreate


# === Настройка тестовой БД ===
SQLALCHEMY_DATABASE_URL = "sqlite:///./db_store/test_api.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


@pytest.fixture(scope="function")
def db_session():
    """Создает новую сессию БД для каждого теста."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Создает тестовый клиент с перекрытой зависимостью get_db."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


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
def test_user(db_session, test_user_data):
    """Создает тестового пользователя в БД через сервис."""
    user_create = UserCreate(
        name=test_user_data["name"],
        password=test_user_data["password"],
        phone=test_user_data["phone"],
    )
    user = register_user_service(user_create, db_session)
    return user


@pytest.fixture
def auth_headers(test_user, test_user_data, client):
    """Получает JWT токен для тестового пользователя."""
    login_data = {
        "login": test_user.login,
        "password": test_user_data["password"],
    }
    response = client.post("/api/v1/users/login", json=login_data)
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_user(db_session):
    """Создает второго пользователя для проверки доступа."""
    user_create = UserCreate(
        name="Другой Пользователь",
        password="otherpass123",
    )
    user = register_user_service(user_create, db_session)
    return user
