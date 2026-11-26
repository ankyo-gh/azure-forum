"""Verify that the running app serves the release and CSS from the deployed ZIP."""

import argparse
import hashlib
import json
import time
from urllib.error import URLError
from urllib.request import Request, urlopen
from zipfile import ZipFile


def fetch(url):
    request = Request(url, headers={"Cache-Control": "no-cache"})
    with urlopen(request, timeout=20) as response:
        return response.read()


def verify_once(base, expected):
    query = "?deployment=" + expected["commit"]
    release = json.loads(fetch(base + "/static/release.json" + query))
    if release != expected:
        raise ValueError("The running release does not match the deployed package")
    css = fetch(base + "/static/css/app.css" + query)
    if hashlib.sha256(css).hexdigest() != expected["css_sha256"]:
        raise ValueError("The served CSS does not match the deployed package")
    if json.loads(fetch(base + "/health" + query)) != {"status": "ok"}:
        raise ValueError("Health check failed")
    html = fetch(base + "/" + query)
    if b"/static/css/app.css" not in html:
        raise ValueError("The index does not reference the application stylesheet")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    parser.add_argument("--package", default="app.zip")
    args = parser.parse_args()
    with ZipFile(args.package) as archive:
        expected = json.loads(archive.read("forum/static/release.json"))
    for attempt in range(1, 13):
        try:
            verify_once(args.base_url.rstrip("/"), expected)
        except (URLError, TimeoutError, OSError, ValueError) as error:
            print(f"Release verification attempt {attempt}/12 failed: {type(error).__name__}")
            if attempt == 12:
                raise SystemExit("The expected release is not being served") from None
            time.sleep(10)
        else:
            print(f"Verified release {expected['commit']}: CSS, health and index match")
            return


if __name__ == "__main__":
    main()
