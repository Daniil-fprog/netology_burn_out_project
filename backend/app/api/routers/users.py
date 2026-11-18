from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.core.access import require_roles
from app.core.enum import RoleCode
from app.db.database import get_db
from app.models.user import UserModel
from app.schemas.user import UserCreate, UserOut
from app.services.user_service import register_user_service


router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/register", response_model=UserOut)
def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
):
    return register_user_service(user_data, db)


@router.get("/me", response_model=UserOut)
def get_me(
    current_user: UserModel = Depends(get_current_user),
):
    return current_user


@router.get("/", response_model=list[UserOut])
def get_users(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    require_roles(db, current_user.id, {RoleCode.SYSTEM_ADMIN})
    return db.query(UserModel).all()

@router.get("/{userId}", response_model=list[UserOut])
def get_user_by_id(
    userId: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    require_roles(db, current_user.id, {RoleCode.SYSTEM_ADMIN})
    return db.query(UserModel).filter(UserModel.id == userId).all()
