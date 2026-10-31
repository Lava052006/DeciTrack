from datetime import datetime, timezone
from uuid import uuid4

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.main import app
from app.models.entities import Meeting, TranscriptSegment
from app.routers import meetings as meeting_routes
from app.schemas.analysis import MeetingAnalysisResponse
from app.services.meeting_analysis import (
    MeetingAnalysisPersistenceError,
    MeetingAnalysisProviderError,
    MeetingAnalysisValidationError,
    analyze_meeting,
)


class Result:
    def __init__(self, matched_count=1):
        self.matched_count = matched_count


class Cursor(list):
    def sort(self, key, direction):
        return Cursor(sorted(self, key=lambda row: row.get(key), reverse=direction < 0))


class Collection:
    def __init__(self, docs=(), fail_insert=False):
        self.docs = [dict(row) for row in docs]
        self.fail_insert = fail_insert

    def find_one(self, query):
        return next((row for row in self.docs if _matches(row, query)), None)

    def find(self, query):
        return Cursor([row for row in self.docs if _matches(row, query)])

    def insert_one(self, doc):
        if self.fail_insert:
            raise RuntimeError("injected insert error")
        self.docs.append(dict(doc))

    def insert_many(self, docs, ordered=True):
        if self.fail_insert:
            # Exercise cleanup after a partial collection write.
            self.docs.extend(dict(row) for row in docs[:1])
            raise RuntimeError("injected insert error")
        self.docs.extend(dict(row) for row in docs)

    def update_one(self, query, update):
        row = self.find_one(query)
        if row is None:
            return Result(0)
        row.update(update["$set"])
        return Result(1)

    def delete_many(self, query):
        self.docs = [row for row in self.docs if not _matches(row, query)]

    def delete_one(self, query):
        row = self.find_one(query)
        if row is not None:
            self.docs.remove(row)


def _matches(row, query):
    for key, value in query.items():
        if key == "$or":
            if not any(_matches(row, option) for option in value):
                return False
        elif isinstance(value, dict) and "$exists" in value:
            if (key in row) != value["$exists"]:
                return False
        elif row.get(key) != value:
            return False
    return True


class FakeDatabase:
    def __init__(self, fail_collection=None):
        self.meeting_id = str(uuid4())
        self.segment_id = str(uuid4())
        meeting = Meeting(id=self.meeting_id, title="Planning", started_at=datetime.now(timezone.utc))
        segment = TranscriptSegment(
            id=self.segment_id,
            meeting_id=self.meeting_id,
            sequence=0,
            speaker="Ada",
            start_time=1.0,
            text="We agree to ship the report. I will send it by Friday.",
        )
        self.collections = {
            "meetings": Collection([meeting.model_dump(mode="python")]),
            "transcript_segments": Collection([segment.model_dump(mode="python")]),
            "meeting_analyses": Collection(fail_insert=fail_collection == "meeting_analyses"),
            "decisions": Collection(fail_insert=fail_collection == "decisions"),
            "action_items": Collection(fail_insert=fail_collection == "action_items"),
            "unresolved_items": Collection(fail_insert=fail_collection == "unresolved_items"),
        }

    def __getitem__(self, name):
        return self.collections[name]


class FakeProvider:
    def __init__(self, response=None, error=None):
        self.response = response if response is not None else _valid_response()
        self.error = error
        self.prompt = None

    def generate_structured(self, prompt, output_model):
        self.prompt = prompt
        if self.error:
            raise self.error
        return self.response


def _valid_response(evidence_id=None):
    evidence_id = evidence_id or str(uuid4())
    return {
        "decisions": [
            {"summary": "Ship the report", "rationale": None, "classification": "confirmed", "evidence_segment_ids": [evidence_id]},
            {"summary": "Consider a dashboard", "classification": "proposed", "evidence_segment_ids": [evidence_id]},
        ],
        "action_items": [
            {"title": "Review figures", "description": None, "owner_name": None, "deadline": None,
             "evidence_segment_ids": [evidence_id]},
        ],
        "commitments": [
            {"title": "Send the report", "owner_name": "Ada", "deadline": None,
             "evidence_segment_ids": [evidence_id]},
        ],
        "unresolved_items": [
            {"description": "Which format is preferred?", "kind": "question", "evidence_segment_ids": [evidence_id]},
            {"description": "Possibly add a dashboard", "kind": "tentative_proposal", "evidence_segment_ids": [evidence_id]},
        ],
    }


def test_analysis_extracts_and_persists_supported_entities():
    db = FakeDatabase()
    provider = FakeProvider(_valid_response(db.segment_id))
    result = analyze_meeting(db.meeting_id, db, provider)

    assert result.version == 1
    assert len(result.decisions) == 2
    assert result.decisions[0].status == "confirmed"
    assert result.decisions[1].status == "proposed"
    assert result.action_items[0].owner_name is None
    assert result.action_items[0].deadline is None
    assert len(result.commitments) == 1 and result.commitments[0].is_commitment
    assert len(result.unresolved_items) == len(result.tentative_proposals) == 1
    assert all(doc["analysis_id"] == result.analysis_id for name in ("decisions", "action_items", "unresolved_items") for doc in db[name].docs)
    assert db["meetings"].docs[0]["analysis_id"] == result.analysis_id
    assert db["meeting_analyses"].docs[0]["status"] == "complete"
    assert db.segment_id in provider.prompt


def test_repeated_analysis_activates_one_new_version_without_mixing_results():
    db = FakeDatabase()
    first = analyze_meeting(db.meeting_id, db, FakeProvider(_valid_response(db.segment_id)))
    second = analyze_meeting(db.meeting_id, db, FakeProvider({"decisions": [], "action_items": [], "commitments": [], "unresolved_items": []}))
    active = db["meetings"].docs[0]["analysis_id"]
    assert second.version == first.version + 1
    assert active == second.analysis_id
    assert second.decisions == [] and second.action_items == []
    assert len(db["decisions"].docs) == 2
    assert all(doc["analysis_id"] == first.analysis_id for doc in db["decisions"].docs)


def test_unknown_evidence_and_malformed_provider_output_are_rejected_without_writes():
    db = FakeDatabase()
    with pytest.raises(MeetingAnalysisValidationError, match="outside meeting"):
        analyze_meeting(db.meeting_id, db, FakeProvider(_valid_response()))
    assert db["meeting_analyses"].docs == []

    malformed = _valid_response(db.segment_id)
    malformed["decisions"][0]["unexpected"] = True
    with pytest.raises(MeetingAnalysisValidationError, match="extraction schema"):
        analyze_meeting(db.meeting_id, db, FakeProvider(malformed))


def test_mongodb_object_ids_are_ignored_but_other_extra_fields_remain_invalid():
    db = FakeDatabase()
    db["meetings"].docs[0]["_id"] = ObjectId()
    db["transcript_segments"].docs[0]["_id"] = ObjectId()
    result = analyze_meeting(db.meeting_id, db, FakeProvider(_valid_response(db.segment_id)))
    assert result.version == 1

    invalid_db = FakeDatabase()
    invalid_db["meetings"].docs[0]["_id"] = ObjectId()
    invalid_db["meetings"].docs[0]["unexpected"] = "still invalid"
    with pytest.raises(MeetingAnalysisPersistenceError, match="stored meeting or transcript is invalid"):
        analyze_meeting(invalid_db.meeting_id, invalid_db, FakeProvider(_valid_response(invalid_db.segment_id)))


def test_provider_failure_and_missing_api_key_are_reported():
    db = FakeDatabase()
    with pytest.raises(MeetingAnalysisProviderError, match="provider failed"):
        analyze_meeting(db.meeting_id, db, FakeProvider(error=RuntimeError("secret provider details")))

    from app.config import settings
    original = settings.gemini_api_key
    settings.gemini_api_key = None
    try:
        with pytest.raises(MeetingAnalysisProviderError, match="GEMINI_API_KEY"):
            analyze_meeting(db.meeting_id, db)
    finally:
        settings.gemini_api_key = original


def test_partial_persistence_failure_cleans_staged_data_and_keeps_old_pointer():
    db = FakeDatabase(fail_collection="action_items")
    db["meetings"].docs[0]["analysis_id"] = "old-analysis"
    db["meetings"].docs[0]["analysis_version"] = 1
    with pytest.raises(MeetingAnalysisPersistenceError, match="analysis persistence failed"):
        analyze_meeting(db.meeting_id, db, FakeProvider(_valid_response(db.segment_id)))
    assert db["meetings"].docs[0]["analysis_id"] == "old-analysis"
    assert db["decisions"].docs == []
    assert db["action_items"].docs == []
    assert db["unresolved_items"].docs == []
    assert db["meeting_analyses"].docs == []


def test_analyze_api_returns_versioned_response(monkeypatch):
    meeting_id = str(uuid4())
    response = MeetingAnalysisResponse(
        meeting_id=meeting_id,
        analysis_id=str(uuid4()),
        version=1,
        decisions=[],
        action_items=[],
        commitments=[],
        unresolved_items=[],
        tentative_proposals=[],
    )
    monkeypatch.setattr(meeting_routes, "analyze_meeting_service", lambda requested, db: response)
    client = TestClient(app)
    try:
        result = client.post(f"/meetings/{meeting_id}/analyze")
    finally:
        client.close()
    assert result.status_code == 200
    assert result.json()["analysis_id"] == response.analysis_id
