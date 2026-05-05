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
    return MongoClient(uri)


def init_mongo(app: Flask) -> None:
    client = _make_client(app.config["MONGO_URI"])
    db = client[app.config["MONGO_DB"]]
    app.extensions["mongo_client"] = client
    app.extensions["mongo_db"] = db

    @app.before_request
    def _ensure_mongo():
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
