"""Schema for the note-to-recommendation association table."""

from app.schemas.common import ORMModel


class NoteRecommendationOut(ORMModel):
    note_id: int
    recommendation_id: int
