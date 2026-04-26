from flask import Flask

from web.auth import auth_bp
from web.dashboard import dashboard_bp
from web.onboarding import onboarding_bp
from web.repositories import InMemoryRepository, MongoRepository
from web.tags import TAG_LABELS


def create_app(config: dict | None = None, repository=None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY="dev",
        MONGODB_URI=None,
        MONGODB_DB_NAME="dizzy_ducks",
    )
    if config:
        app.config.update(config)

    app.repository = repository or _build_repository(app.config)
    app.register_blueprint(auth_bp)
    app.register_blueprint(onboarding_bp)
    app.register_blueprint(dashboard_bp)

    @app.context_processor
    def inject_template_helpers():
        return {"tag_labels": TAG_LABELS}

    return app


def _build_repository(config):
    mongo_uri = config.get("MONGODB_URI")
    if mongo_uri:
        return MongoRepository(
            mongo_uri=mongo_uri,
            db_name=config["MONGODB_DB_NAME"],
        )
    return InMemoryRepository()
