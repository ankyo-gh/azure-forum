"""Build a source-only ZIP for App Service's Oryx remote build."""

import hashlib
import json
import os
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parents[1]
target = root / "dist" / "app.zip"
target.parent.mkdir(exist_ok=True)
commit = (
    os.environ.get("GITHUB_SHA")
    or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
)
release = {
    "commit": commit,
    "css_sha256": hashlib.sha256((root / "forum/static/css/app.css").read_bytes()).hexdigest(),
}
with ZipFile(target, "w", ZIP_DEFLATED) as archive:
    for name in ("app.py", "requirements.txt"):
        archive.write(root / name, name)
    for path in (root / "forum").rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            archive.write(path, path.relative_to(root))
    archive.writestr("forum/static/release.json", json.dumps(release))
print(target)
