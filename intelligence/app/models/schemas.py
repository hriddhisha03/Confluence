from typing import Any

from pydantic import BaseModel, Field


class InferRequest(BaseModel):
    """Unknown keys with one or more sample values each, sent by Processing."""

    samples: dict[str, list[Any]] = Field(..., min_length=1, max_length=500)


class FieldResult(BaseModel):
    name: str
    type: str


class RejectedField(BaseModel):
    name: str
    reason: str


class InferResponse(BaseModel):
    schema_version: int
    registered: list[FieldResult] = Field(default_factory=list)
    existing: list[FieldResult] = Field(default_factory=list)
    rejected: list[RejectedField] = Field(default_factory=list)
