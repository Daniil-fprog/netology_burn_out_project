"""Idempotent reference-data seeds required by the teacher workload application."""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.enum import RoleCode
from app.core.security import hash_password
from app.models.role import RoleModel, UserRoleModel
from app.models.user import UserModel
from app.models.work_type import WorkTypeModel


def seed_roles(db: Session) -> None:
    names = {
        RoleCode.TEACHER: "Преподаватель",
        RoleCode.DIRECTOR: "Директор",
        RoleCode.HEAD: "Глава",
        RoleCode.GROUP_HEAD: "Глава группы",
        RoleCode.SYSTEM_ADMIN: "Системный администратор",
    }
    for code, name in names.items():
        if db.query(RoleModel).filter_by(code=code.value).first() is None:
            db.add(RoleModel(code=code.value, name=name))
    db.commit()


def seed_work_types(db: Session) -> None:
    work_types = (
        ("lessons", "Проведение уроков", "teaching", Decimal("0.1000")),
        ("substitutions", "Замены", "teaching", Decimal("0.1000")),
        ("preparation", "Подготовка к уроку", "teaching_support", Decimal("0.1500")),
        ("grading", "Проверка работ", "teaching_support", Decimal("0.1000")),
        ("documentation", "Документация", "administrative", Decimal("0.0500")),
        ("parent_communication", "Общение с родителями", "communication", Decimal("0.1000")),
        ("class_management", "Классное руководство", "student_support", Decimal("0.1000")),
        ("meetings_methodology", "Совещания и методическая работа", "professional_development", Decimal("0.1000")),
        ("other", "Прочее", "other", Decimal("0.0000")),
    )
    existing = {item.code for item in db.query(WorkTypeModel).all()}
    for code, name, category_group, complexity_weight in work_types:
        if code not in existing:
            db.add(WorkTypeModel(
                code=code,
                name=name,
                category_group=category_group,
                complexity_weight=complexity_weight,
                requires_comment=code == "other",
            ))
    db.commit()


def seed_admin_user(db: Session) -> UserModel:
    user = db.query(UserModel).filter(UserModel.login == "daniil").first()
    if user is None:
        user = UserModel(
            name="Даниил",
            login="daniil",
            phone="+79807057002",
            password_hash=hash_password("admin123"),
        )
        db.add(user)
        db.flush()

    role = db.query(RoleModel).filter_by(code=RoleCode.SYSTEM_ADMIN.value).one()
    if db.query(UserRoleModel).filter_by(user_id=user.id, role_id=role.id).first() is None:
        db.add(UserRoleModel(user_id=user.id, role_id=role.id))
    db.commit()
    db.refresh(user)
    return user
