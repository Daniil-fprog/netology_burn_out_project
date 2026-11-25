from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.database import get_db
from app.schemas.token import TokenOut
from app.schemas.user import UserLogin
from app.services.user_service import authenticate_user_service


router = APIRouter(prefix="/users", tags=["Auth"])


@router.post("/login", response_model=TokenOut)
def login_user(
    user_data: UserLogin,
    db: Session = Depends(get_db),
):
    """Проверяет логин и пароль и возвращает Bearer JWT для последующих запросов."""

    user = authenticate_user_service(user_data, db)

    access_token = create_access_token(data={"sub": str(user.id)})

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }
