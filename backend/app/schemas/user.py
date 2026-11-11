from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# === Pydantic схемы ===
class UserCreate(BaseModel):
    name: str
    login: str
    password: str
    phone: Optional[str] = None


class UserLogin(BaseModel):
    login: str
    password: str = Field(..., min_length=1, description="Пароль не может быть пустым")

class UserOut(BaseModel):
    id: int
    name: str
    login: str
    phone: Optional[str] = None
    is_active: bool
    # The legacy SQLAlchemy model does not mark these columns as NOT NULL.
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)
