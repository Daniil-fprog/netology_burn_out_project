"""Shared Pydantic types for the teacher workload domain."""

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """Base response schema that can read SQLAlchemy model attributes."""

    model_config = ConfigDict(from_attributes=True)
