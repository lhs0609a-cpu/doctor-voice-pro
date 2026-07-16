"""기존 사진 풀 원본을 표시 최대폭(1280) JPEG 로 축소하고 썸네일을 백필한다.

배경:
  예전 업로드 경로는 원본(2816px, 장당 5~7MB)을 그대로 BLOB 에 저장했다.
  그 결과 (1) 볼륨이 차서 업로드가 disk-full 로 죽고,
         (2) 목록 조회가 전체 BLOB 을 메모리로 올려 1GB 머신에서 OOM 이 났다.
  업로드 경로는 이미 고쳤지만 이미 쌓인 사진은 그대로이므로 한 번 정리해야 한다.

특징:
  - 한 장씩 처리 + 주기적 커밋 → 메모리 사용량이 풀 크기와 무관하게 일정.
  - 이미 축소된 사진(1280 이하 + 썸네일 있음)은 건너뛴다 → 중단 후 재실행 안전(멱등).
  - 원본 pHash(original_phash)는 갱신하지 않는다. 유니크화 거리 기준이라 바꾸면
    기존 변형 이력과의 비교 기준이 어긋난다.
  - 마지막에 VACUUM 으로 파일 크기를 실제로 회수한다(SQLite 는 UPDATE 만으로 안 줄어듦).

사용:
  python scripts/shrink_pool_images.py            # 실제 실행
  python scripts/shrink_pool_images.py --dry-run  # 계산만
"""
import io
import os
import sys
import base64
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageOps
from sqlalchemy import create_engine, text

MAX_WIDTH = 1280
JPEG_QUALITY = 88
THUMB_WIDTH = 200
COMMIT_EVERY = 5


def _shrink(data: bytes):
    """(new_bytes, w, h, thumbnail_data_url) 반환. 실패 시 예외."""
    im = Image.open(io.BytesIO(data))
    im = ImageOps.exif_transpose(im)
    im = im.convert("RGB")
    if im.width > MAX_WIDTH:
        h = max(1, round(im.height * MAX_WIDTH / im.width))
        im = im.resize((MAX_WIDTH, h), Image.Resampling.LANCZOS)

    t = im.copy()
    t.thumbnail((THUMB_WIDTH, THUMB_WIDTH))
    tb = io.BytesIO()
    t.save(tb, "JPEG", quality=70)
    thumb = "data:image/jpeg;base64," + base64.b64encode(tb.getvalue()).decode()

    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return buf.getvalue(), im.width, im.height, thumb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_url = os.getenv("DATABASE_URL_SYNC", "sqlite:///./doctorvoice.db")
    print(f"DB: {db_url}")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        n, tot = conn.execute(text(
            "SELECT COUNT(*), COALESCE(SUM(size_bytes),0) FROM pool_images WHERE active=1"
        )).fetchone()
        print(f"대상: {n}장, 현재 {tot/1e6:.1f} MB")
        ids = [r[0] for r in conn.execute(text(
            "SELECT id FROM pool_images WHERE active=1 ORDER BY created_at"
        )).fetchall()]

    if args.dry_run:
        print("--dry-run: 변경 없이 종료")
        return

    done = skipped = failed = 0
    before_total = after_total = 0

    with engine.connect() as conn:
        for i, iid in enumerate(ids, 1):
            row = conn.execute(text(
                "SELECT data, width, thumbnail, size_bytes FROM pool_images WHERE id=:i"
            ), {"i": iid}).fetchone()
            if not row:
                continue
            data, width, thumb, size_bytes = row

            # 이미 축소 + 썸네일까지 있으면 건너뜀(재실행 안전)
            if thumb and width and width <= MAX_WIDTH:
                skipped += 1
                continue

            try:
                new_data, w, h, new_thumb = _shrink(data)
            except Exception as e:
                print(f"  [{i}/{len(ids)}] 실패 {iid[:8]}: {type(e).__name__}")
                failed += 1
                continue

            before_total += size_bytes or len(data)
            after_total += len(new_data)

            conn.execute(text(
                "UPDATE pool_images SET data=:d, width=:w, height=:h, "
                "size_bytes=:s, content_type='image/jpeg', thumbnail=:t WHERE id=:i"
            ), {"d": new_data, "w": w, "h": h, "s": len(new_data), "t": new_thumb, "i": iid})
            done += 1

            if done % COMMIT_EVERY == 0:
                conn.commit()
                print(f"  [{i}/{len(ids)}] {done}장 완료 "
                      f"({before_total/1e6:.0f} -> {after_total/1e6:.0f} MB)")
        conn.commit()

    print(f"\n축소 {done}장 / 건너뜀 {skipped}장 / 실패 {failed}장")
    if done:
        print(f"사진 총량: {before_total/1e6:.1f} MB -> {after_total/1e6:.1f} MB "
              f"({before_total/max(after_total,1):.0f}배 절감)")

    # SQLite 는 UPDATE 만으로 파일이 줄지 않는다. VACUUM 해야 실제 디스크가 회수됨.
    print("\nVACUUM 실행 중...")
    raw = engine.raw_connection()
    try:
        raw.isolation_level = None
        raw.cursor().execute("VACUUM")
        raw.commit()
    finally:
        raw.close()
    print("VACUUM 완료")

    if "sqlite" in db_url and "///" in db_url:
        p = Path(db_url.split("///")[-1])
        if p.exists():
            print(f"DB 파일 크기: {p.stat().st_size/1e6:.1f} MB")


if __name__ == "__main__":
    main()
