"""Exercise the deployed MVP, retaining a clearly labelled acceptance-test post.

Run again with --verify-existing after an App Service restart to test persistence.
The state file contains public post/image URLs only, never credentials or CSRF tokens.
"""

import argparse
import json
import re
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin

import requests
from PIL import Image

STATE = Path(".cache/acceptance.json")


def csrf(response):
    response.raise_for_status()
    return re.search(r'name="csrf_token"[^>]*value="([^"]+)"', response.text)[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url")
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    session = requests.Session()
    assert session.get(base + "/health", timeout=60).json() == {"status": "ok"}
    if args.verify_existing:
        state = json.loads(STATE.read_text())
        assert state["base"] == base
        post_url = state["post_url"]
        image_url = state["image_url"]
    else:
        image = BytesIO()
        Image.new("RGB", (160, 100), "#4f46e5").save(image, "PNG")
        form = session.get(base + "/posts/new", timeout=60)
        response = session.post(
            base + "/posts",
            data={
                "csrf_token": csrf(form),
                "title": "【動作確認】放課後ボードの受入テスト",
                "body": "学校課題の動作確認用投稿です。画像・コメント・再起動後の保存を確認しています。",
                "nickname": "動作確認",
                "category": "study",
            },
            files={"image": ("acceptance.png", image.getvalue(), "image/png")},
            allow_redirects=False,
            timeout=120,
        )
        assert response.status_code == 303, f"Post failed: {response.status_code}"
        post_url = urljoin(base, response.headers["Location"])
        detail = session.get(post_url, timeout=60)
        detail.raise_for_status()
        image_url = urljoin(base, re.search(r'<img[^>]*src="([^"]+)"', detail.text)[1])
        response = session.post(
            post_url + "/comments",
            data={
                "csrf_token": csrf(detail),
                "body": "コメントの保存と表示を確認しました。",
                "nickname": "動作確認",
            },
            allow_redirects=False,
            timeout=60,
        )
        assert response.status_code == 303
        STATE.parent.mkdir(exist_ok=True)
        STATE.write_text(json.dumps({"base": base, "post_url": post_url, "image_url": image_url}))

    detail = session.get(post_url, timeout=60)
    detail.raise_for_status()
    assert "コメントの保存と表示を確認しました。" in detail.text
    image = session.get(image_url, timeout=60)
    image.raise_for_status()
    assert image.headers["Content-Type"].startswith("image/png")
    Image.open(BytesIO(image.content)).verify()
    listing = session.get(base + "/?category=study", timeout=60)
    listing.raise_for_status()
    assert "【動作確認】放課後ボードの受入テスト" in listing.text
    other = session.get(base + "/?category=career", timeout=60)
    other.raise_for_status()
    assert "【動作確認】放課後ボードの受入テスト" not in other.text
    response = session.post(base + "/posts", data={"title": "CSRFなし"}, timeout=60)
    assert response.status_code == 400
    response = session.post(
        post_url + "/comments",
        data={
            "csrf_token": csrf(detail),
            "body": "a" * 501,
        },
        timeout=60,
    )
    assert response.status_code == 400
    print("PASS: health, post, category filter, image, comment, CSRF, validation")
    if args.verify_existing:
        print("PASS: post, comment and image retained after restart")
    print(post_url)


if __name__ == "__main__":
    main()
