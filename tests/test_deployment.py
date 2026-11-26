import hashlib
import json
from unittest.mock import patch

import pytest

from scripts.verify_deployment import verify_once

CSS = b".board { color: green; }"
RELEASE = {"commit": "a" * 40, "css_sha256": hashlib.sha256(CSS).hexdigest()}


def responses(release=RELEASE, css=CSS):
    return [
        json.dumps(release).encode(),
        css,
        b'{"status":"ok"}',
        b'<link rel="stylesheet" href="/static/css/app.css">',
    ]


def test_accepts_the_expected_running_release():
    with patch("scripts.verify_deployment.fetch", side_effect=responses()):
        verify_once("https://example.test", RELEASE)


def test_rejects_old_release_even_when_http_succeeds():
    old_release = {**RELEASE, "commit": "b" * 40}
    with (
        patch("scripts.verify_deployment.fetch", side_effect=responses(release=old_release)),
        pytest.raises(ValueError, match="running release"),
    ):
        verify_once("https://example.test", RELEASE)


def test_rejects_stale_css_even_when_release_matches():
    with (
        patch("scripts.verify_deployment.fetch", side_effect=responses(css=b"old CSS")),
        pytest.raises(ValueError, match="served CSS"),
    ):
        verify_once("https://example.test", RELEASE)
