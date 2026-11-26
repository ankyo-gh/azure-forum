from unittest.mock import MagicMock

import pytest

from forum import create_app


@pytest.fixture
def storage():
    mock = MagicMock()
    mock.list_posts.return_value = []
    mock.list_comments.return_value = []
    mock.get_post.return_value = None
    mock.get_image.return_value = None
    return mock


@pytest.fixture
def app(storage):
    return create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-only-secret",
            "STORAGE": storage,
            "SESSION_COOKIE_SECURE": False,
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()
