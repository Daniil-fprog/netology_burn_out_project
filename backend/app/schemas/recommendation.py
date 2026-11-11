from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RecommendationCreate(BaseModel):
    rec_name: str
    rec_text: str
    mood_type: str  # positive / negative
    score_from: int = 0
    score_to: int = 100


class RecommendationOut(BaseModel):
    id: int
    rec_name: str
    rec_text: str
    mood_type: str
    score_from: int
    score_to: int

    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class RecommendationOutWithNote(BaseModel):
    id: int
    rec_name: str
    rec_text: str

    model_config = ConfigDict(from_attributes=True)
