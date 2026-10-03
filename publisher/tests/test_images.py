import io
import hashlib
import os

from PIL import Image

from publisher.backend.images import publication_image


def source(tmp_path, image, format="PNG", **options):
    buf = io.BytesIO()
    image.save(buf, format=format, **options)
    data = buf.getvalue()
    sha = hashlib.sha256(data).hexdigest()
    (tmp_path / sha).write_bytes(data)
    return sha, data


def test_dense_image_compresses_to_limit_and_preserves_source(tmp_path):
    image = Image.frombytes("RGB", (2000, 1600), os.urandom(2000 * 1600 * 3))
    sha, original = source(tmp_path, image)
    for role, limit in (("body", 1_000_000), ("cover", 2_000_000)):
        path, info = publication_image(tmp_path, sha, role)
        assert info["size"] == path.stat().st_size <= limit
        assert info["width"] <= 2000 and info["height"] <= 1600
        assert (tmp_path / sha).read_bytes() == original
        first = path.read_bytes()
        same, cached = publication_image(tmp_path, sha, role)
        assert same.read_bytes() == first and cached == info


def test_orientation_and_transparency(tmp_path):
    exif = Image.Exif()
    exif[274] = 6
    sha, _ = source(tmp_path, Image.new("RGB", (10, 20), "red"), "JPEG", exif=exif)
    path, info = publication_image(tmp_path, sha, "body")
    with Image.open(path) as image:
        assert image.size == (20, 10)
        assert image.getexif().get(274, 1) == 1
    assert (info["width"], info["height"]) == (20, 10)
    sha, _ = source(tmp_path, Image.new("RGBA", (50, 50), (255, 0, 0, 0)))
    path, info = publication_image(tmp_path, sha, "cover")
    with Image.open(path) as image:
        assert image.getpixel((0, 0))[3] == 0
    assert not info["transparency_flattened"]
    sha, _ = source(tmp_path, Image.new("CMYK", (3000, 100), "white"), "JPEG")
    path, info = publication_image(tmp_path, sha, "body")
    with Image.open(path) as image:
        assert image.mode == "RGB" and image.width == 2560
