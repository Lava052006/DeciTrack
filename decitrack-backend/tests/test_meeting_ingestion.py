from datetime import date

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.models.entities import MeetingStatus
from app.routers import meetings as meeting_routes
from app.schemas.ingestion import MeetingUpload
from app.services.meeting_ingestion import IngestionPersistenceError, ingest_meeting
from app.services.transcript_parser import parse_transcript


class Result:
    def __init__(self, inserted_id=None, matched_count=1):
        self.inserted_id = inserted_id
        self.matched_count = matched_count


class Cursor(list):
    def sort(self, key, direction):
        return Cursor(sorted(self, key=lambda item: item.get(key) or 0, reverse=direction < 0))

    def skip(self, count):
        return Cursor(self[count:])

    def limit(self, count):
        return Cursor(self[:count])


class FakeCollection:
    def __init__(self, fail_insert_many=False):
        self.docs = []
        self.fail_insert_many = fail_insert_many

    def insert_one(self, doc):
        self.docs.append(dict(doc))
        return Result(doc["id"])

    def insert_many(self, docs, ordered=True):
        if self.fail_insert_many:
            raise RuntimeError("database write failed")
        self.docs.extend(dict(doc) for doc in docs)

    def find(self, query=None):
        query = query or {}
        return Cursor([doc for doc in self.docs if all(doc.get(key) == value for key, value in query.items())])

    def find_one(self, query):
        return next(iter(self.find(query)), None)

    def count_documents(self, query):
        return len(self.find(query))

    def update_one(self, query, update):
        doc = self.find_one(query)
        if doc:
            doc.update(update["$set"])
            return Result(matched_count=1)
        return Result(matched_count=0)

    def delete_many(self, query):
        self.docs = [doc for doc in self.docs if doc.get("meeting_id") != query.get("meeting_id")]

    def delete_one(self, query):
        self.docs = [doc for doc in self.docs if doc.get("id") != query.get("id")]


class FakeDatabase:
    def __init__(self, fail_segments=False):
        self.collections = {
            "meetings": FakeCollection(),
            "transcript_segments": FakeCollection(fail_insert_many=fail_segments),
        }

    def __getitem__(self, name):
        return self.collections[name]


def test_parser_normalizes_timestamps_and_preserves_missing_metadata():
    segments = parse_transcript("[00:01:02.5] Alice: Hello\nBob: Reply\nUnattributed text", "m")
    assert [(s.speaker, s.start_time, s.text, s.sequence) for s in segments] == [
        ("Alice", 62.5, "Hello", 0), ("Bob", None, "Reply", 1), (None, None, "Unattributed text", 2)
    ]
    assert parse_transcript("01:30 - Alice: Test", "m")[0].start_time == 90


def test_parser_rejects_empty_transcript():
    with pytest.raises(ValueError):
        parse_transcript(" \n", "m")


def test_upload_persists_meeting_and_segments_then_marks_ready():
    db = FakeDatabase()
    payload = MeetingUpload(title="Review", meeting_date=date(2026, 10, 30), attendees=["Ada"], transcript="Ada: Ready")
    meeting, segments = ingest_meeting(payload, db)
    stored = db["meetings"].docs[0]
    assert meeting.status == MeetingStatus.READY_FOR_ANALYSIS
    assert db["meetings"].docs[0]["status"] == "ready_for_analysis"
    assert len(db["transcript_segments"].docs) == 1
    assert segments[0].meeting_id == meeting.id
    assert meeting.participants == ["Ada"]


def test_upload_rolls_back_meeting_when_segments_fail():
    db = FakeDatabase(fail_segments=True)
    payload = MeetingUpload(title="Review", meeting_date=date.today(), transcript="hello")
    with pytest.raises(IngestionPersistenceError):
        ingest_meeting(payload, db)
    assert db["meetings"].docs == []


def test_upload_schema_rejects_empty_and_invalid_fields():
    with pytest.raises(ValidationError):
        MeetingUpload(title=" ", meeting_date="2026-10-30", transcript="text")
    with pytest.raises(ValidationError):
        MeetingUpload(title="Review", meeting_date="2026-10-30", transcript=" \n")


def test_api_upload_list_detail_transcript_and_invalid_id(monkeypatch):
    db = FakeDatabase()
    monkeypatch.setattr(meeting_routes, "database", db)
    client = TestClient(app)
    try:
        response = client.post("/meetings", json={
            "title": "Review", "meeting_date": "2026-10-30", "attendees": ["Ada"],
            "transcript": "[00:02] Ada: Hello\nMore text",
        })
        assert response.status_code == 201
        meeting_id = response.json()["id"]
        assert response.json()["status"] == "ready_for_analysis"
        assert client.get("/meetings").status_code == 200
        detail = client.get(f"/meetings/{meeting_id}")
        assert detail.status_code == 200 and detail.json()["transcript_segment_count"] == 2
        transcript = client.get(f"/meetings/{meeting_id}/transcript")
        assert transcript.status_code == 200 and len(transcript.json()) == 2
        assert client.get("/meetings/not-a-uuid").status_code == 422
        assert client.get("/meetings/00000000-0000-0000-0000-000000000000").status_code == 404
    finally:
        client.close()


def test_api_returns_persistence_failure(monkeypatch):
    db = FakeDatabase(fail_segments=True)
    monkeypatch.setattr(meeting_routes, "database", db)
    client = TestClient(app)
    try:
        response = client.post("/meetings", json={
            "title": "Review", "meeting_date": "2026-10-30", "transcript": "text"
        })
    finally:
        client.close()
    assert response.status_code == 503
    assert db["meetings"].docs == []
