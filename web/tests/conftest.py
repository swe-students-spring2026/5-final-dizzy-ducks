from __future__ import annotations

import pytest

from web.app import create_app


@pytest.fixture()
def app():
    app = create_app(
        {
            "TESTING": True,
            "MONGO_URI": "mongomock://localhost",
            "MONGO_DB": "test_db",
            "SECRET_KEY": "test",
        }
    )
    return app


@pytest.fixture()
def client(app):
    return app.test_client()
