"""User roles.

The current iteration deliberately implements roles without a permissions
catalog. Fine-grained permissions can be introduced later without changing
the organizational assignment tables.
"""

from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.models.base import TimestampMixin, new_uuid


class RoleModel(TimestampMixin, Base):
    """A system role such as teacher, director, head or group_head."""

    __tablename__ = "roles"

    id = Column(String(36), primary_key=True, default=new_uuid)
    code = Column(String(40), nullable=False, unique=True, index=True)
    name = Column(String(120), nullable=False)
    description = Column(String(500))

    users = relationship("UserRoleModel", back_populates="role")


class UserRoleModel(TimestampMixin, Base):
    """Many-to-many assignment of roles to user accounts."""

    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_role"),)

    id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id = Column(
        String(36),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user = relationship("UserModel", back_populates="roles")
    role = relationship("RoleModel", back_populates="users")
