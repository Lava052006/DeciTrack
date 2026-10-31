from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pymongo.errors import PyMongoError

from app.database.mongodb import database
from app.models.entities import Meeting, TranscriptSegment
from app.schemas.ingestion import MeetingDetail, MeetingUpload
from app.schemas.analysis import MeetingAnalysisResponse
from app.services.meeting_ingestion import IngestionPersistenceError, ingest_meeting
from app.services.meeting_analysis import (
    MeetingAnalysisConflict,
    MeetingAnalysisNotFound,
    MeetingAnalysisPersistenceError,
    MeetingAnalysisProviderError,
    MeetingAnalysisValidationError,
    analyze_meeting as analyze_meeting_service,
)

router = APIRouter(prefix="/meetings", tags=["meetings"])


def _validate_id(meeting_id: str) -> str:
    try:
        return str(UUID(meeting_id))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=422, detail="meeting_id must be a UUID")


@router.post("", response_model=Meeting, status_code=201)
def upload_meeting(payload: MeetingUpload):
    try:
        meeting, _ = ingest_meeting(payload, database)
        return meeting
    except IngestionPersistenceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("", response_model=list[Meeting])
def list_meetings(limit: int = Query(default=50, ge=1, le=200), skip: int = Query(default=0, ge=0)):
    try:
        docs = database["meetings"].find().sort("started_at", -1).skip(skip).limit(limit)
        return [Meeting.model_validate(doc) for doc in docs]
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="could not retrieve meetings") from exc


@router.get("/{meeting_id}", response_model=MeetingDetail)
def get_meeting(meeting_id: str):
    meeting_id = _validate_id(meeting_id)
    try:
        doc = database["meetings"].find_one({"id": meeting_id})
        if not doc:
            raise HTTPException(status_code=404, detail="meeting not found")
        count = database["transcript_segments"].count_documents({"meeting_id": meeting_id})
        return MeetingDetail(meeting=Meeting.model_validate(doc), transcript_segment_count=count)
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="could not retrieve meeting") from exc


@router.get("/{meeting_id}/transcript", response_model=list[TranscriptSegment])
def get_transcript(meeting_id: str):
    meeting_id = _validate_id(meeting_id)
    try:
        if database["meetings"].find_one({"id": meeting_id}) is None:
            raise HTTPException(status_code=404, detail="meeting not found")
        docs = database["transcript_segments"].find({"meeting_id": meeting_id}).sort("sequence", 1)
        return [TranscriptSegment.model_validate(doc) for doc in docs]
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="could not retrieve transcript") from exc


@router.post("/{meeting_id}/analyze", response_model=MeetingAnalysisResponse)
def analyze_meeting(meeting_id: str):
    meeting_id = _validate_id(meeting_id)
    try:
        return analyze_meeting_service(meeting_id, database)
    except MeetingAnalysisNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MeetingAnalysisValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except MeetingAnalysisConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (MeetingAnalysisProviderError, MeetingAnalysisPersistenceError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
