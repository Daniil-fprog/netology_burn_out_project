from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import router as api_v1_router
from app.core.config import CORS_ALLOWED_ORIGINS
from app.db.database import SessionLocal
from app.db.seed import seed_admin_user, seed_roles, seed_work_types
from app.services.survey_service import seed_surveys


# Заполняем БД тестовыми данными
db = SessionLocal()
try:
    seed_roles(db)
    seed_work_types(db)
    seed_admin_user(db)
    seed_surveys(db)
finally:
    db.close()


# === Инициализация FastAPI ===
app = FastAPI(title="MindMOOD App")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["System"])
def health():
    return {"status": "ok"}


# Versioned application API. Infrastructure health checks stay unversioned.
app.include_router(api_v1_router)
