from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.entities import ActionItem, Decision, UnresolvedItem


class _ExtractionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    evidence_segment_ids: list[str] = Field(min_length=1)

    @field_validator("evidence_segment_ids")
    @classmethod
    def evidence_ids_must_be_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("evidence segment IDs must be unique")
        return value


class DecisionExtraction(_ExtractionModel):
    summary: str = Field(min_length=1, max_length=2000)
    rationale: str | None = Field(default=None, max_length=4000)
    classification: Literal["confirmed", "proposed"]


class TaskExtraction(_ExtractionModel):
    title: str = Field(min_length=1, max_length=1000)
    description: str | None = Field(default=None, max_length=4000)
    owner_name: str | None = Field(default=None, max_length=300)
    deadline: datetime | None = None


class UnresolvedExtraction(_ExtractionModel):
    description: str = Field(min_length=1, max_length=2000)
    kind: Literal["question", "tentative_proposal"]


class MeetingExtraction(BaseModel):
    """Strict structured response expected from an LLM provider."""

    model_config = ConfigDict(extra="forbid")

    decisions: list[DecisionExtraction] = Field(default_factory=list)
    action_items: list[TaskExtraction] = Field(default_factory=list)
    commitments: list[TaskExtraction] = Field(default_factory=list)
    unresolved_items: list[UnresolvedExtraction] = Field(default_factory=list)


class MeetingAnalysisResponse(BaseModel):
    meeting_id: str
    analysis_id: str
    version: int
    decisions: list[Decision]
    action_items: list[ActionItem]
    commitments: list[ActionItem]
    unresolved_items: list[UnresolvedItem]
    tentative_proposals: list[UnresolvedItem]
