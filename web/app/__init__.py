from __future__ import annotations

import os
from pathlib import Path

from flask import Flask
from jinja2 import ChoiceLoader, FileSystemLoader

from web.auth import auth_bp
from web.dashboard import dashboard_bp
from web.onboarding import onboarding_bp
from web.repositories import InMemoryRepository, MongoRepository
from web.sample_data import seed_sample_gigs
from web.tags import TAG_LABELS

from .blueprints.dev_auth import bp as dev_auth_bp
from .blueprints.management import bp as management_bp
from .blueprints.profile import bp as profile_bp
from .db import close_mongo, init_mongo

DEFAULT_MONGO_URI = "mongodb://localhost:27017"


def create_app(test_config: dict | None = None, repository=None) -> Flask:
    app = Flask(__name__, static_folder="../static", template_folder="../templates")
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret"),
        MONGO_URI=os.environ.get("MONGO_URI", DEFAULT_MONGO_URI),
        MONGO_DB=os.environ.get(
            "MONGO_DB", os.environ.get("MONGODB_DB_NAME", "campus_gigs")
        ),
        MONGODB_URI=os.environ.get("MONGODB_URI"),
        MONGODB_DB_NAME=os.environ.get(
            "MONGODB_DB_NAME", os.environ.get("MONGO_DB", "campus_gigs")
        ),
        SEED_SAMPLE_GIGS=os.environ.get("SEED_SAMPLE_GIGS", "1") != "0",
        TESTING=False,
    )

    if test_config:
        app.config.update(test_config)

    _sync_mongo_config(app)
    _configure_template_loader(app)

    init_mongo(app)
    app.repository = repository or _build_repository(app)
    if (
        repository is None
        and app.config["SEED_SAMPLE_GIGS"]
        and isinstance(app.repository, InMemoryRepository)
    ):
        seed_sample_gigs(app.repository)

    app.register_blueprint(auth_bp)
    app.register_blueprint(dev_auth_bp, name="dev_auth")
    app.register_blueprint(onboarding_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(management_bp)
    app.register_blueprint(profile_bp)

    @app.context_processor
    def inject_template_helpers():
        return {"tag_labels": TAG_LABELS}

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    app.teardown_appcontext(close_mongo)
    return app


def _sync_mongo_config(app: Flask) -> None:
    if app.config.get("MONGODB_URI") and app.config["MONGO_URI"] == DEFAULT_MONGO_URI:
        app.config["MONGO_URI"] = app.config["MONGODB_URI"]
    if app.config.get("MONGO_DB") and not app.config.get("MONGODB_DB_NAME"):
        app.config["MONGODB_DB_NAME"] = app.config["MONGO_DB"]
    if app.config.get("MONGODB_DB_NAME") and not app.config.get("MONGO_DB"):
        app.config["MONGO_DB"] = app.config["MONGODB_DB_NAME"]


def _configure_template_loader(app: Flask) -> None:
    web_root = Path(__file__).resolve().parents[1]
    app.jinja_loader = ChoiceLoader(
        [
            FileSystemLoader(str(web_root / "templates")),
            FileSystemLoader(str(web_root / "app" / "templates")),
        ]
    )


def _build_repository(app: Flask):
    mongo_uri = _repository_mongo_uri(app)
    if mongo_uri:
        return MongoRepository(
            client=app.extensions["mongo_client"],
            db_name=app.config["MONGO_DB"],
        )
    return InMemoryRepository()


def _repository_mongo_uri(app: Flask) -> str | None:
    if app.config.get("MONGODB_URI"):
        return app.config["MONGODB_URI"]
    if os.environ.get("MONGO_URI"):
        return app.config["MONGO_URI"]
    if app.config["MONGO_URI"] != DEFAULT_MONGO_URI:
        return app.config["MONGO_URI"]
    return None
