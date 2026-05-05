from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from flask import Flask, current_app, g
from pymongo import MongoClient


@dataclass(frozen=True)
class MongoHandle:
    client: Any
    db: Any


def _make_client(uri: str):
    if uri.startswith("mongomock://"):
        import mongomock  # noqa: PLC0415
        return mongomock.MongoClient()
    # Use a short timeout so serverless cold starts fail fast if Atlas is unreachable
    # (e.g. IP not whitelisted). Vercel functions have dynamic IPs; Atlas must allow 0.0.0.0/0.
    return MongoClient(uri, serverSelectionTimeoutMS=5000)


def init_mongo(app: Flask) -> None:
    try:
        client = _make_client(app.config["MONGO_URI"])
        db = client[app.config["MONGO_DB"]]
        app.extensions["mongo_client"] = client
        app.extensions["mongo_db"] = db
    except Exception as exc:  # noqa: BLE001
        app.logger.warning("MongoDB unavailable (%s) — using in-memory store", exc)
        app.extensions["mongo_client"] = None
        app.extensions["mongo_db"] = None

    @app.before_request
    def _ensure_mongo():
        if app.extensions.get("mongo_client") is not None:
            _ensure_handle()


def _ensure_handle() -> MongoHandle:
    if "mongo" in g:
        return g.mongo
    client = current_app.extensions["mongo_client"]
    db = current_app.extensions["mongo_db"]
    g.mongo = MongoHandle(client=client, db=db)
    return g.mongo


def get_db():
    return _ensure_handle().db


def close_mongo(_err: Optional[BaseException] = None) -> None:
    handle = g.pop("mongo", None)
    if handle is None:
        return
    # The Mongo client is stored on the app (shared across requests).
    # Closing it here breaks subsequent requests (PyMongo raises "Cannot use MongoClient after close").
    return
