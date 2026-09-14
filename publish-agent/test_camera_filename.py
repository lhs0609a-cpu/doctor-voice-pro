"""업로드 파일 이름이 사진 EXIF(기종·촬영시각)에 맞게 붙는지. python -m pytest test_camera_filename.py -q"""
import io
import re

import pytest

from plan import camera_filename, exif_make_and_time

Image = pytest.importorskip("PIL.Image")   # 실행기 자체엔 Pillow 가 없다 — 테스트용 JPEG 만드는 데만 쓴다


def _jpeg(make=None, when=None) -> bytes:
    ex = Image.Exif()
    if make:
        ex[0x010F] = make
    if when:
        ex[0x8769] = {0x9003: when}
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), (1, 2, 3)).save(buf, "JPEG", exif=ex.tobytes())
    return buf.getvalue()


def test_reads_make_and_shot_time():
    make, when = exif_make_and_time(_jpeg("samsung", "2026:08:12 14:35:12"))
    assert make == "samsung" and when.strftime("%Y%m%d_%H%M%S") == "20260812_143512"


def test_names_follow_camera_brand():
    when = "2026:08:12 14:35:12"
    assert camera_filename(_jpeg("samsung", when)) == "20260812_143512.jpg"
    assert camera_filename(_jpeg("Xiaomi", when)) == "IMG_20260812_143512.jpg"
    assert re.fullmatch(r"IMG_\d{4}\.JPG", camera_filename(_jpeg("Apple", when)))
    assert re.fullmatch(r"DSC\d{5}\.JPG", camera_filename(_jpeg("SONY", when)))


def test_same_photo_same_name_and_never_old_pattern():
    data = _jpeg()
    assert camera_filename(data) == camera_filename(data)
    assert not camera_filename(data).startswith("image_")


def test_non_jpeg_and_broken_data_keep_extension():
    assert camera_filename(b"\x89PNG\r\n\x1a\nxxxx", "png").endswith(".png")
    assert camera_filename(b"\xff\xd8\xff\xe1\x00", "jpg").endswith(".jpg")
