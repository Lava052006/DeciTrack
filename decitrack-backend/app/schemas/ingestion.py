from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models.entities import Meeting


class MeetingUpload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=300)
    meeting_date: date | datetime
    attendees: list[str] = Field(default_factory=list)
    transcript: str = Field(min_length=1)

    @field_validator("title")
    @classmethod
    def title_not_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("title must not be blank")
        return value.strip()

    @field_validator("transcript")
    @classmethod
    def transcript_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("transcript must not be blank")
        return value

    @field_validator("attendees")
    @classmethod
    def clean_attendees(cls, value: list[str]) -> list[str]:
        attendees = [attendee.strip() for attendee in value]
        if any(not attendee for attendee in attendees):
            raise ValueError("attendees must not contain blank names")
        return attendees


class MeetingDetail(BaseModel):
    meeting: Meeting
    transcript_segment_count: int
