from pymongo.collection import Collection

from app.database.mongodb import database


COLLECTION_INDEXES: dict[str, list[tuple[list[tuple[str, int]], dict]]] = {
    "meetings": [([("id", 1)], {"unique": True}), ([ ("status", 1), ("started_at", -1)], {})],
    "transcript_segments": [([("id", 1)], {"unique": True}), ([ ("meeting_id", 1), ("sequence", 1)], {"unique": True})],
    "decisions": [([("id", 1)], {"unique": True}), ([ ("meeting_id", 1), ("status", 1)], {}), ([ ("owner_id", 1)], {})],
    "decision_history": [([("id", 1)], {"unique": True}), ([ ("decision_id", 1), ("created_at", -1)], {})],
    "action_items": [([("id", 1)], {"unique": True}), ([ ("meeting_id", 1), ("status", 1)], {}), ([ ("owner_id", 1), ("status", 1)], {}), ([ ("deadline", 1)], {})],
    "action_history": [([("id", 1)], {"unique": True}), ([ ("action_item_id", 1), ("created_at", -1)], {})],
    "conflicts": [([("id", 1)], {"unique": True}), ([ ("meeting_id", 1), ("status", 1)], {})],
    "unresolved_items": [([("id", 1)], {"unique": True}), ([ ("meeting_id", 1), ("status", 1)], {}), ([ ("owner_id", 1)], {})],
    "approvals": [([("id", 1)], {"unique": True}), ([ ("meeting_id", 1), ("status", 1)], {}), ([ ("decision_id", 1), ("status", 1)], {}), ([ ("approver_id", 1), ("status", 1)], {})],
}


def initialize_collections(db=database) -> None:
    """Create each collection and its indexes; safe to run on every app startup."""
    existing = set(db.list_collection_names())
    for name, indexes in COLLECTION_INDEXES.items():
        if name not in existing:
            db.create_collection(name)
        collection: Collection = db[name]
        for keys, options in indexes:
            collection.create_index(keys, **options)
