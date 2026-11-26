import re
from datetime import UTC, datetime
from io import BytesIO

import pytest
from azure.core.exceptions import HttpResponseError
from PIL import Image
from werkzeug.datastructures import MultiDict

POST_ID = "8000000000000-" + "a" * 32


def token(client, path="/posts/new"):
    response = client.get(path)
    return re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', response.data)[1].decode()


def post_entity(**changes):
    return {
        "RowKey": POST_ID,
        "title": "テスト投稿",
        "body": "本文",
        "nickname": "匿名",
        "category": "study",
        "image_blob": "",
        "created_at": datetime(2026, 11, 26, tzinfo=UTC),
        **changes,
    }


def test_health_and_empty_pages(client):
    assert client.get("/health").json == {"status": "ok"}
    assert "まだ投稿がありません" in client.get("/").text
    assert client.get("/posts/new").status_code == 200


def test_post_success_and_escaping(client, storage):
    storage.create_post.return_value = POST_ID
    response = client.post(
        "/posts",
        data={
            "csrf_token": token(client),
            "title": "<script>alert(1)</script>",
            "body": "本文",
            "category": "study",
            "nickname": "  ",
        },
    )
    assert response.status_code == 303
    storage.create_post.assert_called_once()
    assert storage.create_post.call_args[0][0]["nickname"] == "匿名"
    storage.get_post.return_value = post_entity(title="<script>alert(1)</script>")
    detail = client.get(response.location)
    assert "&lt;script&gt;" in detail.text
    assert "<script>alert(1)</script>" not in detail.text
    assert "2026/11/26 09:00" in detail.text


@pytest.mark.parametrize(
    "field,value",
    [
        ("title", ""),
        ("title", "a" * 81),
        ("body", " " * 3),
        ("body", "a" * 2001),
        ("nickname", "a" * 21),
        ("category", "all"),
        ("category", "unknown"),
    ],
)
def test_invalid_post(client, storage, field, value):
    data = {
        "csrf_token": token(client),
        "title": "保持するタイトル",
        "body": "本文",
        "category": "study",
    }
    data[field] = value
    response = client.post("/posts", data=data)
    assert response.status_code == 400
    storage.create_post.assert_not_called()


def test_post_maximum_lengths(client, storage):
    storage.create_post.return_value = POST_ID
    response = client.post(
        "/posts",
        data={
            "csrf_token": token(client),
            "title": "あ" * 80,
            "body": "い" * 2000,
            "nickname": "う" * 20,
            "category": "chat",
        },
    )
    assert response.status_code == 303


def test_csrf_is_enforced(client, storage):
    response = client.post("/posts", data={"title": "test", "body": "test", "category": "study"})
    assert response.status_code == 400
    storage.create_post.assert_not_called()


def test_category_filter(client, storage):
    for category in ("study", "school", "career", "hobby", "chat"):
        assert client.get("/?category=" + category).status_code == 200
        storage.list_posts.assert_called_with(category)
    assert client.get("/?category=unknown").status_code == 404


def test_comments(client, storage):
    storage.get_post.return_value = post_entity()
    csrf = token(client, "/posts/" + POST_ID)
    response = client.post(
        f"/posts/{POST_ID}/comments", data={"csrf_token": csrf, "body": "ありがとう"}
    )
    assert response.status_code == 303
    storage.create_comment.assert_called_once_with(
        POST_ID, {"nickname": "匿名", "body": "ありがとう"}
    )
    for body in ("", " ", "a" * 501):
        assert (
            client.post(
                f"/posts/{POST_ID}/comments", data={"csrf_token": csrf, "body": body}
            ).status_code
            == 400
        )
    assert (
        client.post(
            f"/posts/{POST_ID}/comments", data={"csrf_token": csrf, "body": "a" * 500}
        ).status_code
        == 303
    )
    assert (
        client.post(f"/posts/{POST_ID}/comments", data={"body": "csrf missing"}).status_code == 400
    )


def test_missing_post_and_image(client, storage):
    assert client.get("/posts/invalid").status_code == 404
    assert client.get("/posts/" + POST_ID).status_code == 404
    assert (
        client.post(
            f"/posts/{POST_ID}/comments", data={"csrf_token": token(client), "body": "hello"}
        ).status_code
        == 404
    )
    assert client.get("/images/invalid.png").status_code == 404
    assert client.get("/images/" + "a" * 32 + ".png").status_code == 404
    storage.create_comment.assert_not_called()


def test_storage_errors_are_private(client, storage):
    storage.list_posts.side_effect = HttpResponseError("secret-storage-connection")
    response = client.get("/")
    assert response.status_code == 503
    assert b"secret-storage-connection" not in response.data


def test_upload_and_image_delivery(client, storage):
    image = BytesIO()
    Image.new("RGB", (8, 8)).save(image, format="PNG")
    image.seek(0)
    storage.create_post.return_value = POST_ID
    assert (
        client.post(
            "/posts",
            data={
                "csrf_token": token(client),
                "title": "画像",
                "body": "本文",
                "category": "hobby",
                "image": (image, "wrong-extension.txt"),
            },
        ).status_code
        == 303
    )
    saved_image = storage.create_post.call_args[0][1]
    assert saved_image[1:] == ("png", "image/png")
    storage.get_image.return_value = (saved_image[0], saved_image[2])
    response = client.get("/images/" + "a" * 32 + ".png")
    assert response.status_code == 200
    assert response.mimetype == "image/png"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_invalid_image_and_preserved_form(client, storage):
    response = client.post(
        "/posts",
        data={
            "csrf_token": token(client),
            "title": "保持するタイトル",
            "body": "保持する本文",
            "category": "study",
            "image": (BytesIO(b"<script>not an image</script>"), "fake.png"),
        },
    )
    assert response.status_code == 400
    assert "保持するタイトル" in response.text
    assert "保持する本文" in response.text
    storage.create_post.assert_not_called()


def test_multiple_images_rejected(client, storage):
    data = MultiDict(
        [
            ("csrf_token", token(client)),
            ("title", "test"),
            ("body", "body"),
            ("category", "study"),
            ("image", (BytesIO(b"a"), "a.png")),
            ("image", (BytesIO(b"b"), "b.png")),
        ]
    )
    assert client.post("/posts", data=data).status_code == 400
    storage.create_post.assert_not_called()


def test_request_limit(client):
    assert (
        client.post(
            "/posts", data=b"a" * (6 * 1024 * 1024 + 1), content_type="application/octet-stream"
        ).status_code
        == 413
    )
