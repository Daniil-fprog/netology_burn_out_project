"""Version 1 application API router."""

from fastapi import APIRouter

from app.api.routers import auth, schools, surveys, teachers, users, work_types, workload


router = APIRouter(prefix="/api/v1")


@router.get("/home", tags=["System"])
def home():
    return {"message": "FastAPI работает"}


router.include_router(auth.router)
router.include_router(users.router)
router.include_router(schools.router)
router.include_router(teachers.router)
router.include_router(work_types.router)
router.include_router(workload.router)
router.include_router(surveys.router)
