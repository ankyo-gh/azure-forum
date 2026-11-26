from io import BytesIO

import pytest
from PIL import Image, PngImagePlugin
from werkzeug.datastructures import FileStorage

from forum.images import MAX_IMAGE_BYTES, sanitize_image


@pytest.mark.parametrize(
    "format,ext,mime",
    [
        ("JPEG", "jpg", "image/jpeg"),
        ("PNG", "png", "image/png"),
        ("WEBP", "webp", "image/webp"),
    ],
)
def test_real_format_and_metadata_removal(format, ext, mime):
    source = BytesIO()
    exif = Image.Exif()
    exif[270] = "private metadata"
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("location", "private location")
    Image.new("RGB", (10, 10), "red").save(source, format=format, exif=exif, pnginfo=metadata)
    source.seek(0)
    data, actual_ext, actual_mime = sanitize_image(FileStorage(source, filename="wrong.gif"))
    assert (actual_ext, actual_mime) == (ext, mime)
    with Image.open(BytesIO(data)) as result:
        assert not result.getexif()
        assert "location" not in result.info


def test_size_and_pixel_limits():
    with pytest.raises(ValueError, match="5 MiB"):
        sanitize_image(FileStorage(BytesIO(b"a" * (MAX_IMAGE_BYTES + 1))))
    source = BytesIO()
    Image.new("1", (5000, 5000)).save(source, "PNG")
    source.seek(0)
    with pytest.raises(ValueError, match="画素"):
        sanitize_image(FileStorage(source))


def test_gif_and_truncated_images_rejected():
    source = BytesIO()
    Image.new("RGB", (10, 10)).save(source, "GIF")
    source.seek(0)
    with pytest.raises(ValueError):
        sanitize_image(FileStorage(source))
    with pytest.raises(ValueError):
        sanitize_image(FileStorage(BytesIO(b"\x89PNG\r\n\x1a\n")))
