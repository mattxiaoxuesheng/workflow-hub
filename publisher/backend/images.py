"""Immutable source images and reproducible WeChat publication copies."""

import io
import json
import secrets
from pathlib import Path

from PIL import Image, ImageOps

LIMITS = {"body": 1_000_000, "cover": 2_000_000}


def publication_image(blobs: Path, sha: str, role: str):
    """Cache derived bytes separately; original content and hash never change."""
    limit = LIMITS[role]
    cache = blobs / ".publication-v1"
    cache.mkdir(exist_ok=True)
    stem = cache / f"{sha}-{role}"
    info_path = stem.with_suffix(".json")
    output = stem.with_suffix(".img")
    if info_path.exists() and output.exists():
        return output, json.loads(info_path.read_text())
    source = (blobs / sha).read_bytes()
    with Image.open(io.BytesIO(source)) as original:
        if original.width * original.height > 40_000_000:
            raise ValueError("图片最多4000万像素")
        image = ImageOps.exif_transpose(original)
        image.load()
        width, height = image.size
        orientation = original.getexif().get(274, 1)
        original_format = original.format
    image.thumbnail((2560, 2560), Image.Resampling.LANCZOS)
    flattened = False
    quality = None
    if (
        original_format in ("JPEG", "PNG")
        and len(source) <= limit
        and image.size == (width, height)
        and orientation == 1
    ):
        data = source
        mime = "image/png" if original_format == "PNG" else "image/jpeg"
    else:
        # Lossless PNG protects text/graphics and transparency when it fits.
        if image.mode not in ("1", "L", "LA", "P", "RGB", "RGBA"):
            image = image.convert("RGB")
        buf = io.BytesIO()
        image.save(buf, format="PNG", optimize=True)
        data = buf.getvalue()
        mime = "image/png"
        if len(data) > limit:
            flattened = "A" in image.getbands() or "transparency" in image.info
            if flattened:
                rgba = image.convert("RGBA")
                rgb = Image.new("RGB", image.size, "white")
                rgb.paste(rgba, mask=rgba.getchannel("A"))
                image = rgb
            else:
                image = image.convert("RGB")
            mime = "image/jpeg"
            while True:
                for quality in (92, 85, 75, 65, 55):
                    buf = io.BytesIO()
                    image.save(buf, format="JPEG", quality=quality, optimize=True)
                    data = buf.getvalue()
                    if len(data) <= limit:
                        break
                if len(data) <= limit:
                    break
                image = image.resize(
                    (max(1, int(image.width * 0.8)), max(1, int(image.height * 0.8))),
                    Image.Resampling.LANCZOS,
                )
    info = {
        "role": role,
        "original_size": len(source),
        "original_width": width,
        "original_height": height,
        "size": len(data),
        "width": image.width,
        "height": image.height,
        "mime": mime,
        "limit": limit,
        "quality": quality,
        "transparency_flattened": flattened,
    }
    # Publish data before its metadata; interrupted writes can be regenerated.
    token = secrets.token_hex(8)
    temp = cache / f"{sha}-{role}-{token}.tmp"
    temp.write_bytes(data)
    temp.replace(output)
    temp = cache / f"{sha}-{role}-{token}.json.tmp"
    temp.write_text(json.dumps(info))
    temp.replace(info_path)
    return output, info
