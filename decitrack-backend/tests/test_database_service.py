from app.services.database import COLLECTION_INDEXES, initialize_collections


class FakeCollection:
    def __init__(self):
        self.indexes = []

    def create_index(self, keys, **options):
        self.indexes.append((keys, options))


class FakeDatabase:
    def __init__(self, existing=()):
        self.names = set(existing)
        self.collections = {}

    def list_collection_names(self):
        return list(self.names)

    def create_collection(self, name):
        self.names.add(name)
        self.collections[name] = FakeCollection()

    def __getitem__(self, name):
        return self.collections.setdefault(name, FakeCollection())


def test_initializer_creates_all_collections_and_indexes_idempotently():
    db = FakeDatabase()
    initialize_collections(db)
    assert db.names == set(COLLECTION_INDEXES)
    for name, expected_indexes in COLLECTION_INDEXES.items():
        assert len(db.collections[name].indexes) == len(expected_indexes)
    initialize_collections(db)
    assert db.names == set(COLLECTION_INDEXES)


def test_history_collections_are_separate():
    assert "decision_history" in COLLECTION_INDEXES
    assert "action_history" in COLLECTION_INDEXES
