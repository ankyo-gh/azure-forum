import warnings
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 20_000_000
FORMATS = {
    "JPEG": ("jpg", "image/jpeg"),
    "PNG": ("png", "image/png"),
    "WEBP": ("webp", "image/webp"),
}


def sanitize_image(upload):
    data = upload.stream.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("画像は5 MiB以下にしてください。")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                image_format = source.format
                if image_format not in FORMATS:
                    raise ValueError("JPEG・PNG・WebPの画像を選んでください。")
                if source.width * source.height > MAX_PIXELS:
                    raise ValueError("画像は2,000万画素以下にしてください。")
                source.load()
                oriented = ImageOps.exif_transpose(source)
                mode = "RGBA" if "A" in oriented.getbands() and image_format != "JPEG" else "RGB"
                # A new pixel-only image drops EXIF, ICC, text, location and other metadata.
                clean = Image.new(mode, oriented.size)
                clean.paste(oriented.convert(mode))
                output = BytesIO()
                clean.save(output, format=image_format)
                extension, content_type = FORMATS[image_format]
                return output.getvalue(), extension, content_type
    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        raise ValueError("画像を読み込めません。有効なJPEG・PNG・WebPを選んでください。") from error
