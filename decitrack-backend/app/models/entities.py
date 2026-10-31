from datetime import datetime, timezone
from enum import StrEnum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class Entity(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)
    id: str = Field(default_factory=new_id)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("id")
    @classmethod
    def valid_uuid_id(cls, value: str) -> str:
        return str(UUID(value))


class MeetingStatus(StrEnum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DecisionStatus(StrEnum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    REVERSED = "reversed"


class ActionStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ConflictStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class UnresolvedStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Meeting(Entity):
    title: str = Field(min_length=1, max_length=300)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    participants: list[str] = Field(default_factory=list)
    status: MeetingStatus = MeetingStatus.SCHEDULED
    source: Optional[str] = None


class TranscriptSegment(Entity):
    meeting_id: str
    text: str = Field(min_length=1)
    speaker: Optional[str] = None
    start_time: Optional[float] = Field(default=None, ge=0)
    end_time: Optional[float] = Field(default=None, ge=0)
    sequence: int = Field(ge=0)


class Decision(Entity):
    meeting_id: str
    summary: str = Field(min_length=1)
    rationale: Optional[str] = None
    status: DecisionStatus = DecisionStatus.PROPOSED
    owner_id: Optional[str] = None
    evidence_ids: list[str] = Field(default_factory=list)


class ActionItem(Entity):
    meeting_id: str
    title: str = Field(min_length=1)
    description: Optional[str] = None
    status: ActionStatus = ActionStatus.OPEN
    owner_id: Optional[str] = None
    deadline: Optional[datetime] = None
    evidence_ids: list[str] = Field(default_factory=list)


class Conflict(Entity):
    meeting_id: str
    description: str = Field(min_length=1)
    decision_ids: list[str] = Field(default_factory=list)
    status: ConflictStatus = ConflictStatus.OPEN
    evidence_ids: list[str] = Field(default_factory=list)


class UnresolvedItem(Entity):
    meeting_id: str
    description: str = Field(min_length=1)
    owner_id: Optional[str] = None
    status: UnresolvedStatus = UnresolvedStatus.OPEN
    evidence_ids: list[str] = Field(default_factory=list)


class Approval(Entity):
    meeting_id: str
    decision_id: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_by: Optional[str] = None
    approver_id: Optional[str] = None
    responded_at: Optional[datetime] = None
    evidence_ids: list[str] = Field(default_factory=list)
