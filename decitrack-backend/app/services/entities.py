from typing import TypeVar

from pydantic import BaseModel
from pymongo.database import Database

from app.database.mongodb import database

T = TypeVar("T", bound=BaseModel)


def save_entity(collection_name: str, entity: T, db: Database = database) -> T:
    """Insert a validated entity document into its dedicated collection."""
    db[collection_name].insert_one(entity.model_dump(mode="python"))
    return entity


def get_entity(collection_name: str, entity_id: str, model: type[T], db: Database = database) -> T | None:
    """Load an entity by its public UUID string ID."""
    document = db[collection_name].find_one({"id": entity_id})
    return model.model_validate(document) if document else None


def record_history(history_collection: str, entity_id: str, snapshot: BaseModel, db: Database = database) -> None:
    """Append an immutable snapshot to decision_history or action_history."""
    if history_collection not in {"decision_history", "action_history"}:
        raise ValueError("history_collection must be decision_history or action_history")
    document = snapshot.model_dump(mode="python")
    document["decision_id" if history_collection == "decision_history" else "action_item_id"] = entity_id
    db[history_collection].insert_one(document)
