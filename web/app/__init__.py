from __future__ import annotations

import os

from flask import Flask

from .blueprints.dev_auth import bp as auth_bp
from .blueprints.gigs import bp as gigs_bp
from .blueprints.management import bp as management_bp
from .blueprints.profile import bp as profile_bp
from .db import close_mongo, init_mongo


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)

    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret"),
        MONGO_URI=os.environ.get("MONGO_URI", "mongodb://localhost:27017"),
        MONGO_DB=os.environ.get("MONGO_DB", "campus_gigs"),
        TESTING=False,
    )

    if test_config:
        app.config.update(test_config)

    init_mongo(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(gigs_bp)
    app.register_blueprint(management_bp)
    app.register_blueprint(profile_bp)

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    app.teardown_appcontext(close_mongo)
    return app
