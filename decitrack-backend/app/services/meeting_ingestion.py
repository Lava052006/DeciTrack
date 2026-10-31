from datetime import date, datetime, time, timezone

from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.models.entities import Meeting, MeetingStatus, TranscriptSegment
from app.schemas.ingestion import MeetingUpload
from app.services.transcript_parser import parse_transcript


class IngestionPersistenceError(Exception):
    """Raised when a meeting or its transcript cannot be persisted."""


class DuplicateMeetingSourceError(IngestionPersistenceError):
    """Raised when a unique source identifier was persisted concurrently."""


def _as_datetime(value: date | datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def ingest_meeting(
    payload: MeetingUpload,
    db: Database,
    source_identifier: str | None = None,
) -> tuple[Meeting, list[TranscriptSegment]]:
    meeting = Meeting(
        title=payload.title,
        started_at=_as_datetime(payload.meeting_date),
        participants=payload.attendees,
        status=MeetingStatus.SCHEDULED,
        source=source_identifier,
    )
    segments = parse_transcript(payload.transcript, meeting.id)
    meeting_saved = False
    try:
        db["meetings"].insert_one(meeting.model_dump(mode="python"))
        meeting_saved = True
        if segments:
            db["transcript_segments"].insert_many(
                [segment.model_dump(mode="python") for segment in segments], ordered=True
            )
        meeting.status = MeetingStatus.READY_FOR_ANALYSIS
        meeting.updated_at = datetime.now(timezone.utc)
        result = db["meetings"].update_one({"id": meeting.id}, {"$set": {
            "status": MeetingStatus.READY_FOR_ANALYSIS.value,
            "updated_at": meeting.updated_at,
        }})
        if result.matched_count != 1:
            raise RuntimeError("meeting readiness update did not match the inserted meeting")
    except Exception as exc:
        # Best effort rollback keeps incomplete uploads out of the analysis queue.
        try:
            db["transcript_segments"].delete_many({"meeting_id": meeting.id})
            if meeting_saved:
                db["meetings"].delete_one({"id": meeting.id})
        except Exception:
            pass
        if source_identifier is not None and isinstance(exc, DuplicateKeyError):
            raise DuplicateMeetingSourceError("meeting source identifier already exists") from exc
        raise IngestionPersistenceError("could not persist meeting and transcript") from exc
    return meeting, segments
