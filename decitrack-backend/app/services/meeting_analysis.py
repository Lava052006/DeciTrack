"""LLM extraction, evidence validation, and versioned meeting analysis storage."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import ValidationError
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.llm.gemini import GeminiProvider
from app.llm.provider import LLMProvider, LLMProviderError
from app.models.entities import ActionItem, Decision, Meeting, TranscriptSegment, UnresolvedItem, utc_now
from app.schemas.analysis import MeetingAnalysisResponse, MeetingExtraction


class MeetingAnalysisError(RuntimeError):
    pass


class MeetingAnalysisNotFound(MeetingAnalysisError):
    pass


class MeetingAnalysisValidationError(MeetingAnalysisError):
    pass


class MeetingAnalysisProviderError(MeetingAnalysisError):
    pass


class MeetingAnalysisPersistenceError(MeetingAnalysisError):
    pass


class MeetingAnalysisConflict(MeetingAnalysisError):
    pass


def _without_mongo_id(document: Any) -> Any:
    """Drop only MongoDB's internal ObjectId before strict model validation."""
    if isinstance(document, dict) and "_id" in document:
        return {key: value for key, value in document.items() if key != "_id"}
    return document


def _prompt(segments: list[TranscriptSegment]) -> str:
    transcript = [
        {
            "segment_id": segment.id,
            "sequence": segment.sequence,
            "speaker": segment.speaker,
            "start_time_seconds": segment.start_time,
            "text": segment.text,
        }
        for segment in segments
    ]
    return (
        "Analyze this meeting transcript and return only the requested structured data. "
        "A confirmed decision requires explicit agreement or a clear final decision. "
        "Keep suggestions and tentative proposals unconfirmed. A commitment requires an "
        "explicit promise or acceptance of responsibility; do not turn vague discussion "
        "into a commitment. Never infer an owner or deadline. Use null when the transcript "
        "does not explicitly supply one. Every extracted claim must cite one or more exact "
        "segment_id values from the transcript. Do not invent IDs or facts. When evidence "
        "is insufficient, omit the claim. Classify unresolved questions as question and "
        "tentative proposals as tentative_proposal.\n\nTRANSCRIPT SEGMENTS:\n"
        + json.dumps(transcript, ensure_ascii=False)
    )


def _validate_evidence(extraction: MeetingExtraction, meeting_id: str, segments: list[TranscriptSegment]) -> None:
    available = {segment.id: segment for segment in segments}
    claims = [*extraction.decisions, *extraction.action_items, *extraction.commitments, *extraction.unresolved_items]
    for claim in claims:
        for evidence_id in claim.evidence_segment_ids:
            segment = available.get(evidence_id)
            if segment is None or segment.meeting_id != meeting_id:
                raise MeetingAnalysisValidationError(
                    f"analysis cited a transcript segment outside meeting {meeting_id}"
                )


def _decode_extraction(raw: Any) -> MeetingExtraction:
    try:
        if isinstance(raw, MeetingExtraction):
            return raw
        if isinstance(raw, str):
            return MeetingExtraction.model_validate_json(raw)
        return MeetingExtraction.model_validate(raw)
    except (ValidationError, ValueError, TypeError) as exc:
        raise MeetingAnalysisValidationError("LLM response did not match the extraction schema") from exc


def _cleanup(db: Database, analysis_id: str) -> bool:
    """Remove all unactivated writes for one failed analysis version."""
    try:
        for collection in ("decisions", "action_items", "unresolved_items"):
            db[collection].delete_many({"analysis_id": analysis_id})
        db["meeting_analyses"].delete_one({"id": analysis_id})
        return True
    except Exception:
        return False


def _insert_many(db: Database, collection: str, entities: list[Any]) -> None:
    if entities:
        db[collection].insert_many(
            [entity.model_dump(mode="python") for entity in entities], ordered=True
        )


def analyze_meeting(
    meeting_id: str,
    db: Database,
    provider: LLMProvider | None = None,
) -> MeetingAnalysisResponse:
    """Analyze stored segments and activate a complete, evidence-linked version."""
    try:
        meeting_doc = db["meetings"].find_one({"id": meeting_id})
    except Exception as exc:
        raise MeetingAnalysisPersistenceError("could not retrieve meeting for analysis") from exc
    if meeting_doc is None:
        raise MeetingAnalysisNotFound("meeting not found")
    try:
        meeting = Meeting.model_validate(_without_mongo_id(meeting_doc))
        segment_docs = db["transcript_segments"].find({"meeting_id": meeting_id}).sort("sequence", 1)
        segments = [
            TranscriptSegment.model_validate(_without_mongo_id(document))
            for document in segment_docs
        ]
    except Exception as exc:
        raise MeetingAnalysisPersistenceError("stored meeting or transcript is invalid") from exc
    if not segments:
        raise MeetingAnalysisValidationError("meeting has no transcript segments to analyze")
    if any(segment.meeting_id != meeting_id for segment in segments):
        raise MeetingAnalysisValidationError("transcript contains a segment from another meeting")

    llm = provider
    if llm is None:
        try:
            llm = GeminiProvider()
        except LLMProviderError as exc:
            raise MeetingAnalysisProviderError(str(exc)) from exc
    try:
        extraction = _decode_extraction(llm.generate_structured(_prompt(segments), MeetingExtraction))
    except MeetingAnalysisValidationError:
        raise
    except LLMProviderError as exc:
        raise MeetingAnalysisProviderError("LLM provider failed to analyze the meeting") from exc
    except Exception as exc:
        raise MeetingAnalysisProviderError("LLM provider failed to analyze the meeting") from exc
    _validate_evidence(extraction, meeting_id, segments)

    previous_version = meeting.analysis_version
    version = (previous_version or 0) + 1
    analysis_id = str(uuid4())
    decisions = [
        Decision(
            meeting_id=meeting_id,
            summary=claim.summary,
            rationale=claim.rationale,
            status="confirmed" if claim.classification == "confirmed" else "proposed",
            evidence_ids=claim.evidence_segment_ids,
            analysis_id=analysis_id,
            analysis_version=version,
        )
        for claim in extraction.decisions
    ]
    actions = [
        ActionItem(
            meeting_id=meeting_id,
            title=claim.title,
            description=claim.description,
            owner_name=claim.owner_name,
            deadline=claim.deadline,
            evidence_ids=claim.evidence_segment_ids,
            is_commitment=is_commitment,
            analysis_id=analysis_id,
            analysis_version=version,
        )
        for is_commitment, claims in ((False, extraction.action_items), (True, extraction.commitments))
        for claim in claims
    ]
    unresolved = [
        UnresolvedItem(
            meeting_id=meeting_id,
            description=claim.description,
            kind=claim.kind,
            evidence_ids=claim.evidence_segment_ids,
            analysis_id=analysis_id,
            analysis_version=version,
        )
        for claim in extraction.unresolved_items
    ]

    analysis_doc = {
        "id": analysis_id,
        "meeting_id": meeting_id,
        "version": version,
        "status": "pending",
        "created_at": utc_now(),
    }
    try:
        db["meeting_analyses"].insert_one(analysis_doc)
        _insert_many(db, "decisions", decisions)
        _insert_many(db, "action_items", actions)
        _insert_many(db, "unresolved_items", unresolved)
        record_update = db["meeting_analyses"].update_one(
            {"id": analysis_id},
            {"$set": {"status": "complete", "completed_at": datetime.now(timezone.utc)}},
        )
        if record_update.matched_count != 1:
            raise RuntimeError("analysis staging record disappeared before activation")
        if previous_version is None:
            version_filter = {"$or": [{"analysis_version": None}, {"analysis_version": {"$exists": False}}]}
        else:
            version_filter = {"analysis_version": previous_version}
        update_result = db["meetings"].update_one(
            {"id": meeting_id, **version_filter},
            {"$set": {"analysis_id": analysis_id, "analysis_version": version}},
        )
        if update_result.matched_count != 1:
            raise MeetingAnalysisConflict("another analysis completed concurrently; retry the request")
    except DuplicateKeyError as exc:
        _cleanup(db, analysis_id)
        raise MeetingAnalysisConflict("another analysis is already creating this version") from exc
    except MeetingAnalysisConflict:
        if not _cleanup(db, analysis_id):
            raise MeetingAnalysisPersistenceError("analysis conflict; cleanup of staged results failed")
        raise
    except Exception as exc:
        cleaned = _cleanup(db, analysis_id)
        message = "analysis persistence failed" if cleaned else "analysis persistence failed and staged cleanup was incomplete"
        raise MeetingAnalysisPersistenceError(message) from exc

    return MeetingAnalysisResponse(
        meeting_id=meeting_id,
        analysis_id=analysis_id,
        version=version,
        decisions=decisions,
        action_items=[item for item in actions if not item.is_commitment],
        commitments=[item for item in actions if item.is_commitment],
        unresolved_items=[item for item in unresolved if item.kind == "question"],
        tentative_proposals=[item for item in unresolved if item.kind == "tentative_proposal"],
    )
