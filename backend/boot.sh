#!/bin/sh
# 부팅은 가벼워야 한다.
#
# 서버가 죽으면(배포·OOM) 이 과정을 처음부터 다시 거친 뒤에야 요청을 받기 시작한다.
# 그 사이 들어온 로그인·발행은 거절되는 것이 아니라 **매달려 있다**(Fly 300초 ·
# 홈페이지 180초 타임아웃). 그래서 사람 눈에는 오류가 아니라 '무한 로딩'으로 보이고,
# 대기 글이 많으면 뜨는 즉시 또 큰 묶음을 집어 다시 죽는 일이 반복됐다(2026-10-27).
#
# 스키마를 맞추는 일(init_db · alembic)은 **새 버전을 배포할 때 한 번만** 필요하다.
# 같은 이미지로 다시 뜨는 것에는 바뀐 것이 없는데도 앱을 두 번 더 import 하고
# (init_db · alembic) 마이그레이션을 전부 훑고 있었다. 이미지 식별자를 볼륨에 적어
# 두고 같으면 건너뛴다. 실패하면 표시를 남기지 않으므로 다음 부팅에 다시 시도한다.
#
# 표를 만드는 것 자체는 app/main.py 의 lifespan 이 모든 모델에 대해 늘 한 번 더
# 확인한다(create_all + 컬럼 추가). 그래서 건너뛰어도 빈 DB 가 방치되지 않는다.
set -e

MARK=/data/.schema-ready
STAMP="${FLY_IMAGE_REF:-local}"

if [ "$STAMP" != "local" ] && [ "$(cat "$MARK" 2>/dev/null)" = "$STAMP" ]; then
  echo "[boot] 스키마는 이미 이 버전으로 맞춰져 있습니다 — 초기화·마이그레이션을 건너뜁니다"
else
  echo "[boot] 새 버전입니다 — 스키마를 맞춥니다 ($STAMP)"
  python init_db.py
  alembic upgrade head
  # 볼륨에 적지 못해도 부팅은 계속한다(그러면 예전처럼 매번 맞출 뿐이다).
  printf '%s' "$STAMP" > "$MARK" 2>/dev/null || echo "[boot] 표시를 남기지 못했습니다 — 다음 부팅에도 맞춥니다"
fi

exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
