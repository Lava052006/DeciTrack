"""Import a Wispr meeting through the existing Phase 3 ingestion pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pymongo.database import Database

from app.integrations.wispr.normalizer import normalize_meeting
from app.integrations.wispr.service import WisprMeetingService, WisprRetrievalError
from app.models.entities import Meeting, TranscriptSegment
from app.services.meeting_ingestion import (
    DuplicateMeetingSourceError,
    IngestionPersistenceError,
    ingest_meeting,
)


class WisprImportError(RuntimeError):
    """Base error for importing a Wispr meeting into DeciTrack."""


class WisprImportRetrievalError(WisprImportError):
    pass


class WisprImportNormalizationError(WisprImportError):
    pass


class WisprImportPersistenceError(WisprImportError):
    pass


@dataclass(frozen=True)
class WisprImportResult:
    meeting: Meeting
    segments: list[TranscriptSegment]
    imported: bool

    @property
    def decitrack_meeting_id(self) -> str:
        return self.meeting.id


def _find_existing(db: Database, source_id: str) -> dict[str, Any] | None:
    try:
        return db["meetings"].find_one({"source": source_id})
    except Exception as exc:
        raise WisprImportPersistenceError(
            f"could not check whether Wispr meeting {source_id!r} was already imported"
        ) from exc


async def import_wispr_meeting(
    meeting_id: str,
    db: Database,
    wispr_service: Any | None = None,
) -> WisprImportResult:
    """Retrieve, normalize, and persist a Wispr meeting once per source ID.

    MongoDB's unique sparse index on ``meetings.source`` arbitrates concurrent
    imports. The preflight lookup is an optimization; duplicate-key recovery is
    the correctness mechanism.
    """
    if not isinstance(meeting_id, str) or not meeting_id.strip():
        raise ValueError("meeting_id must be a non-empty string")

    existing = _find_existing(db, meeting_id)
    if existing is not None:
        return WisprImportResult(
            meeting=Meeting.model_validate(existing),
            segments=[],
            imported=False,
        )

    service = wispr_service or WisprMeetingService()
    try:
        retrieved = await service.get_meeting(meeting_id)
    except WisprRetrievalError as exc:
        raise WisprImportRetrievalError(f"could not retrieve Wispr meeting {meeting_id!r}") from exc
    except Exception as exc:
        raise WisprImportRetrievalError(f"could not retrieve Wispr meeting {meeting_id!r}") from exc

    try:
        normalized = normalize_meeting(retrieved["meeting"], retrieved["transcript"])
    except Exception as exc:
        raise WisprImportNormalizationError(
            f"could not normalize Wispr meeting {meeting_id!r}"
        ) from exc
    if normalized.source_meeting_id != meeting_id:
        raise WisprImportNormalizationError(
            "retrieved Wispr meeting ID does not match the requested source ID"
        )

    try:
        meeting, segments = ingest_meeting(
            normalized.upload,
            db,
            source_identifier=normalized.source_meeting_id,
        )
        return WisprImportResult(meeting=meeting, segments=segments, imported=True)
    except DuplicateMeetingSourceError as exc:
        # Another request won the unique-index race. Resolve its local ID.
        existing = _find_existing(db, meeting_id)
        if existing is None:
            raise WisprImportPersistenceError(
                "source identifier conflicted but the imported meeting could not be found"
            ) from exc
        return WisprImportResult(
            meeting=Meeting.model_validate(existing),
            segments=[],
            imported=False,
        )
    except IngestionPersistenceError as exc:
        raise WisprImportPersistenceError(
            f"could not persist Wispr meeting {meeting_id!r}"
        ) from exc
