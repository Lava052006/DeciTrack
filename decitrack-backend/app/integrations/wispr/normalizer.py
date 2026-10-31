"""Convert Wispr meeting records into the Phase 3 transcript representation."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.entities import TranscriptSegment
from app.schemas.ingestion import MeetingUpload
from app.services.transcript_parser import parse_transcript


class NormalizedWisprMeeting(BaseModel):
    """Phase 3 upload fields plus source identity and normalized segments."""

    model_config = ConfigDict(extra="forbid")

    upload: MeetingUpload
    source_meeting_id: str
    segments: list[TranscriptSegment]


def _first(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return None


def _meeting_date(value: Any) -> date | datetime:
    if isinstance(value, (date, datetime)):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                return date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("Wispr meeting has an invalid start timestamp") from exc
    raise ValueError("Wispr meeting has no usable start timestamp")


def normalize_meeting(meeting: dict[str, Any], transcript: str) -> NormalizedWisprMeeting:
    """Normalize raw Wispr details without supplying absent fields."""
    if not isinstance(meeting, dict):
        raise ValueError("Wispr meeting details must be an object")
    source_id = _first(meeting, "id", "meeting_id")
    title = meeting.get("title")
    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError("Wispr meeting has no source meeting ID")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Wispr meeting has no usable title")
    if not isinstance(transcript, str) or not transcript.strip():
        raise ValueError("Wispr meeting transcript is empty")

    attendees = _first(meeting, "attendees", "participants") or []
    names = []
    for attendee in attendees:
        if isinstance(attendee, str):
            names.append(attendee)
        elif isinstance(attendee, dict):
            name = attendee.get("name")
            if isinstance(name, str) and name.strip():
                names.append(name)

    upload = MeetingUpload(
        title=title,
        meeting_date=_meeting_date(_first(meeting, "start_time", "started_at", "start")),
        attendees=names,
        transcript=transcript,
    )
    # The established parser retains ordering and parses only explicit speaker
    # and timestamp annotations. Its output is used unchanged for Phase 3.
    segments = parse_transcript(transcript, source_id)
    return NormalizedWisprMeeting(
        upload=upload,
        source_meeting_id=source_id,
        segments=segments,
    )
