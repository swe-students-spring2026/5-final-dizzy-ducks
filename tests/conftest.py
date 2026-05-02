import pytest

from web import create_app
from web.repositories import InMemoryRepository


@pytest.fixture
def repository():
    return InMemoryRepository()


@pytest.fixture
def app(repository):
    app = create_app(
        {"SECRET_KEY": "test-secret", "TESTING": True},
        repository=repository,
    )
    return app


@pytest.fixture
def client(app):
    return app.test_client()
