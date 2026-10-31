import asyncio
from datetime import date

import pytest
from pymongo.errors import DuplicateKeyError

from app.integrations.wispr.ingestion import (
    WisprImportNormalizationError,
    WisprImportPersistenceError,
    WisprImportRetrievalError,
    import_wispr_meeting,
)
from app.services.database import COLLECTION_INDEXES
from app.services.meeting_ingestion import ingest_meeting
from app.schemas.ingestion import MeetingUpload


class Result:
    matched_count = 1


class FakeCollection:
    def __init__(self, fail_segments=False):
        self.docs = []
        self.fail_segments = fail_segments

    def find_one(self, query):
        return next((doc for doc in self.docs if all(doc.get(k) == v for k, v in query.items())), None)

    def insert_one(self, doc):
        if doc.get("source") is not None and self.find_one({"source": doc["source"]}):
            raise DuplicateKeyError("duplicate source")
        self.docs.append(dict(doc))

    def insert_many(self, docs, ordered=True):
        if self.fail_segments:
            raise RuntimeError("segment insert failed")
        self.docs.extend(dict(doc) for doc in docs)

    def update_one(self, query, update):
        doc = self.find_one(query)
        if doc:
            doc.update(update["$set"])
        return Result()

    def delete_many(self, query):
        self.docs = [doc for doc in self.docs if doc.get("meeting_id") != query.get("meeting_id")]

    def delete_one(self, query):
        self.docs = [doc for doc in self.docs if doc.get("id") != query.get("id")]


class FakeDatabase:
    def __init__(self, fail_segments=False):
        self.collections = {
            "meetings": FakeCollection(),
            "transcript_segments": FakeCollection(fail_segments=fail_segments),
        }

    def __getitem__(self, name):
        return self.collections[name]


class FakeWisprService:
    def __init__(self, response=None, error=None, barrier=None):
        self.response = response or {
            "meeting": {
                "id": "wispr-source-1",
                "title": "Planning",
                "start_time": "2026-10-30T12:00:00Z",
                "attendees": ["Ada"],
            },
            "transcript": "[00:01] Ada: We should ship",
        }
        self.error = error
        self.barrier = barrier
        self.calls = 0

    async def get_meeting(self, meeting_id):
        self.calls += 1
        if self.barrier:
            self.barrier[0].set()
            await self.barrier[1].wait()
        if self.error:
            raise self.error
        return self.response


@pytest.mark.asyncio
async def test_wispr_import_persists_through_phase3_and_stores_source_id():
    db = FakeDatabase()
    result = await import_wispr_meeting("wispr-source-1", db, FakeWisprService())
    assert result.imported is True
    assert result.decitrack_meeting_id == result.meeting.id
    assert db["meetings"].docs[0]["source"] == "wispr-source-1"
    assert len(db["transcript_segments"].docs) == 1
    assert db["transcript_segments"].docs[0]["meeting_id"] == result.meeting.id


@pytest.mark.asyncio
async def test_existing_import_returns_existing_decitrack_id_without_retrieval():
    db = FakeDatabase()
    first = await import_wispr_meeting("wispr-source-1", db, FakeWisprService())
    service = FakeWisprService(error=RuntimeError("must not be called"))
    duplicate = await import_wispr_meeting("wispr-source-1", db, service)
    assert duplicate.imported is False
    assert duplicate.decitrack_meeting_id == first.decitrack_meeting_id
    assert service.calls == 0


@pytest.mark.asyncio
async def test_concurrent_imports_converge_on_unique_source_record():
    db = FakeDatabase()
    both_entered = asyncio.Event()
    release = asyncio.Event()

    class ConcurrentWisprService(FakeWisprService):
        async def get_meeting(self, meeting_id):
            self.calls += 1
            if self.calls == 2:
                both_entered.set()
            await release.wait()
            return self.response

    service = ConcurrentWisprService()
    tasks = [
        asyncio.create_task(import_wispr_meeting("wispr-source-1", db, service)),
        asyncio.create_task(import_wispr_meeting("wispr-source-1", db, service)),
    ]
    await asyncio.wait_for(both_entered.wait(), timeout=2)
    release.set()
    first, second = await asyncio.gather(*tasks)
    assert first.decitrack_meeting_id == second.decitrack_meeting_id
    assert sorted([first.imported, second.imported]) == [False, True]
    assert len(db["meetings"].docs) == 1


@pytest.mark.asyncio
async def test_retrieval_normalization_and_persistence_failures_are_clear():
    with pytest.raises(WisprImportRetrievalError):
        await import_wispr_meeting("wispr-source-1", FakeDatabase(), FakeWisprService(error=RuntimeError("offline")))

    malformed = FakeWisprService(response={"meeting": {"id": "wrong"}, "transcript": "text"})
    with pytest.raises(WisprImportNormalizationError):
        await import_wispr_meeting("wispr-source-1", FakeDatabase(), malformed)

    with pytest.raises(WisprImportPersistenceError):
        await import_wispr_meeting("wispr-source-1", FakeDatabase(fail_segments=True), FakeWisprService())


def test_manual_phase3_ingestion_remains_unchanged_and_source_index_is_unique():
    db = FakeDatabase()
    payload = MeetingUpload(
        title="Manual", meeting_date=date(2026, 10, 30), transcript="Manual transcript"
    )
    meeting, _ = ingest_meeting(payload, db)
    assert meeting.source is None
    assert db["meetings"].docs[0]["source"] is None

    source_indexes = [
        options for keys, options in COLLECTION_INDEXES["meetings"] if keys == [("source", 1)]
    ]
    assert source_indexes == [{"unique": True, "partialFilterExpression": {"source": {"$type": "string"}}}]
