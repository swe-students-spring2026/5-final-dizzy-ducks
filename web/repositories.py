from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

from web.tags import normalize_tags


class DuplicateEmailError(ValueError):
    """Raised when a user signs up with an email that already exists."""


DEFAULT_NOTIFICATION_PREFERENCES = {
    "tags": [],
    "new_gig_alerts": True,
    "application_alerts": True,
    "status_alerts": True,
    "weekly_digest": True,
}


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _default_preferences(tags: list[str] | None = None) -> dict[str, Any]:
    preferences = deepcopy(DEFAULT_NOTIFICATION_PREFERENCES)
    preferences["tags"] = normalize_tags(tags or [])
    return preferences


def _serialize_user(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None

    serialized = deepcopy(document)
    serialized["id"] = str(serialized.pop("_id"))
    serialized.setdefault("skills", [])
    serialized.setdefault("notification_preferences", _default_preferences())
    serialized["notification_preferences"].setdefault("tags", [])
    serialized.setdefault("tags", serialized["notification_preferences"]["tags"])
    return serialized


def _serialize_gig(document: dict[str, Any]) -> dict[str, Any]:
    serialized = deepcopy(document)
    serialized["id"] = str(serialized.pop("_id"))
    return serialized


@dataclass
class InMemoryRepository:
    users: dict[str, dict[str, Any]] = field(default_factory=dict)
    gigs: dict[str, dict[str, Any]] = field(default_factory=dict)
    _next_user_id: int = 1
    _next_gig_id: int = 1
    _lock: RLock = field(default_factory=RLock)

    def create_user(
        self, *, name: str, email: str, password_hash: str
    ) -> dict[str, Any]:
        normalized_email = normalize_email(email)
        with self._lock:
            if any(user["email"] == normalized_email for user in self.users.values()):
                raise DuplicateEmailError(normalized_email)

            user_id = str(self._next_user_id)
            self._next_user_id += 1
            self.users[user_id] = {
                "_id": user_id,
                "name": name.strip(),
                "email": normalized_email,
                "password_hash": password_hash,
                "skills": [],
                "notification_preferences": _default_preferences(),
                "created_at": datetime.now(timezone.utc),
            }
            return _serialize_user(self.users[user_id])

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        normalized_email = normalize_email(email)
        for user in self.users.values():
            if user["email"] == normalized_email:
                return _serialize_user(user)
        return None

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        return _serialize_user(self.users.get(str(user_id)))

    def update_user_tags(self, user_id: str, tags: list[str]) -> dict[str, Any] | None:
        user = self.users.get(str(user_id))
        if user is None:
            return None

        user["notification_preferences"]["tags"] = normalize_tags(tags)
        user["tags"] = user["notification_preferences"]["tags"]
        return _serialize_user(user)

    def update_user_profile(
        self, user_id: str, *, name: str | None = None, tags: list[str] | None = None
    ) -> dict[str, Any] | None:
        user = self.users.get(str(user_id))
        if user is None:
            return None

        if name:
            user["name"] = name.strip()
        if tags is not None:
            user["notification_preferences"]["tags"] = normalize_tags(tags)
            user["tags"] = user["notification_preferences"]["tags"]
        return _serialize_user(user)

    def create_gig(
        self,
        *,
        title: str,
        category: str,
        pay: str,
        location: str,
        date: str,
        description: str,
        poster_id: str,
        status: str = "open",
    ) -> dict[str, Any]:
        with self._lock:
            gig_id = str(self._next_gig_id)
            self._next_gig_id += 1
            self.gigs[gig_id] = {
                "_id": gig_id,
                "title": title,
                "category": category,
                "pay": pay,
                "location": location,
                "date": date,
                "description": description,
                "poster_id": poster_id,
                "status": status,
                "created_at": datetime.now(timezone.utc),
            }
            return _serialize_gig(self.gigs[gig_id])

    def list_open_gigs(
        self, *, tags: list[str] | None = None, search: str = ""
    ) -> list[dict[str, Any]]:
        normalized_tags = normalize_tags(tags or [])
        search_text = search.strip().lower()

        matches = []
        for gig in self.gigs.values():
            if gig.get("status") != "open":
                continue
            if normalized_tags and gig.get("category") not in normalized_tags:
                continue
            if search_text and not _gig_matches_search(gig, search_text):
                continue
            matches.append(_serialize_gig(gig))

        return sorted(matches, key=lambda gig: gig["created_at"], reverse=True)

    def list_gigs_by_poster(self, poster_id: str) -> list[dict[str, Any]]:
        matches = [
            _serialize_gig(gig)
            for gig in self.gigs.values()
            if str(gig.get("poster_id")) == str(poster_id)
        ]
        return sorted(matches, key=lambda gig: gig["created_at"], reverse=True)


class MongoRepository:
    def __init__(self, *, mongo_uri: str | None = None, db_name: str, client=None):
        if client is None:
            from pymongo import MongoClient

            client = MongoClient(mongo_uri)

        self.db = client[db_name]
        self.users = self.db.users
        self.gigs = self.db.gigs
        self.users.create_index("email", unique=True)
        self.gigs.create_index([("status", ASCENDING), ("category", ASCENDING)])

    def create_user(
        self, *, name: str, email: str, password_hash: str
    ) -> dict[str, Any]:
        document = {
            "name": name.strip(),
            "email": normalize_email(email),
            "password_hash": password_hash,
            "skills": [],
            "notification_preferences": _default_preferences(),
            "created_at": datetime.now(timezone.utc),
        }
        try:
            result = self.users.insert_one(document)
        except DuplicateKeyError as exc:
            raise DuplicateEmailError(email) from exc

        document["_id"] = result.inserted_id
        return _serialize_user(document)

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        return _serialize_user(self.users.find_one({"email": normalize_email(email)}))

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        try:
            object_id = ObjectId(user_id)
        except (InvalidId, TypeError):
            return None

        return _serialize_user(self.users.find_one({"_id": object_id}))

    def update_user_tags(self, user_id: str, tags: list[str]) -> dict[str, Any] | None:
        try:
            object_id = ObjectId(user_id)
        except (InvalidId, TypeError):
            return None

        normalized_tags = normalize_tags(tags)
        result = self.users.find_one_and_update(
            {"_id": object_id},
            {"$set": {"notification_preferences.tags": normalized_tags}},
            return_document=True,
        )
        return _serialize_user(result)

    def update_user_profile(
        self, user_id: str, *, name: str | None = None, tags: list[str] | None = None
    ) -> dict[str, Any] | None:
        try:
            object_id = ObjectId(user_id)
        except (InvalidId, TypeError):
            return None

        updates: dict[str, Any] = {}
        if name:
            updates["name"] = name.strip()
        if tags is not None:
            normalized_tags = normalize_tags(tags)
            updates["tags"] = normalized_tags
            updates["notification_preferences.tags"] = normalized_tags
        if not updates:
            return self.get_user_by_id(user_id)

        result = self.users.find_one_and_update(
            {"_id": object_id},
            {"$set": updates},
            return_document=True,
        )
        return _serialize_user(result)

    def create_gig(
        self,
        *,
        title: str,
        category: str,
        pay: str,
        location: str,
        date: str,
        description: str,
        poster_id: str,
        status: str = "open",
    ) -> dict[str, Any]:
        document = {
            "title": title,
            "category": category,
            "pay": pay,
            "location": location,
            "date": date,
            "description": description,
            "poster_id": poster_id,
            "status": status,
            "created_at": datetime.now(timezone.utc),
        }
        result = self.gigs.insert_one(document)
        document["_id"] = result.inserted_id
        return _serialize_gig(document)

    def list_open_gigs(
        self, *, tags: list[str] | None = None, search: str = ""
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"status": "open"}
        normalized_tags = normalize_tags(tags or [])
        if normalized_tags:
            query["category"] = {"$in": normalized_tags}

        search_text = search.strip()
        if search_text:
            regex = {"$regex": re.escape(search_text), "$options": "i"}
            query["$or"] = [
                {"title": regex},
                {"description": regex},
                {"location": regex},
                {"category": regex},
            ]

        documents = self.gigs.find(query).sort("created_at", DESCENDING)
        return [_serialize_gig(document) for document in documents]

    def list_gigs_by_poster(self, poster_id: str) -> list[dict[str, Any]]:
        poster_keys: list[Any] = [poster_id]
        try:
            poster_keys.append(ObjectId(poster_id))
        except (InvalidId, TypeError):
            pass

        documents = self.gigs.find({"poster_id": {"$in": poster_keys}}).sort(
            "created_at", DESCENDING
        )
        return [_serialize_gig(document) for document in documents]


def _gig_matches_search(gig: dict[str, Any], search_text: str) -> bool:
    searchable = (
        gig.get("title", ""),
        gig.get("description", ""),
        gig.get("location", ""),
        gig.get("category", ""),
    )
    return any(search_text in value.lower() for value in searchable)
