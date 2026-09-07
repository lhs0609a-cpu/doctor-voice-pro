"""별도 프로세스 워커 진입점: `python -m app.worker` (backend 디렉터리에서).

앱과 같은 DB 를 보며 background_jobs 를 처리한다. RUN_WORKER_IN_APP=false 로 두면
API 서버는 작업을 적재만 하고 이 프로세스가 실행한다.
"""
import asyncio
import logging

from app.services.job_worker import run_forever

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


if __name__ == "__main__":
    try:
        asyncio.run(run_forever())
    except KeyboardInterrupt:
        pass
