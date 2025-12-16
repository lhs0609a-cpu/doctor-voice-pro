"""
데이터베이스 초기화 스크립트
"""
import os
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine
from app.db.database import Base
from app.core.config import settings

# 모든 모델 import (중요!)
from app.models import (
    User,
    DoctorProfile,
    Post,
    PostVersion,
    PostAnalytics,
    MedicalLawRule,
    NaverConnection,
    Tag,
)

def init_database():
    """데이터베이스 초기화"""
    print("=" * 60)
    print("데이터베이스 초기화 시작")
    print("=" * 60)

    # 데이터베이스 URL
    db_url = os.getenv("DATABASE_URL_SYNC", "sqlite:///./doctorvoice.db")
    print(f"데이터베이스 URL: {db_url}")

    # /data 디렉토리 확인 및 생성
    data_dir = Path("/data")
    if data_dir.exists():
        print(f"✓ /data 디렉토리 존재")
        print(f"  권한: {oct(data_dir.stat().st_mode)[-3:]}")
    else:
        print("✗ /data 디렉토리가 없습니다")
        # 로컬 디렉토리 사용
        data_dir = Path("./")
        print(f"✓ 로컬 디렉토리 사용: {data_dir.absolute()}")

    # 데이터베이스 파일 경로 확인
    if "sqlite" in db_url:
        db_file = db_url.split("///")[-1] if "///" in db_url else "doctorvoice.db"
        db_path = Path(db_file)
        print(f"데이터베이스 파일: {db_path.absolute()}")

        # 디렉토리 생성
        db_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"✓ 디렉토리 생성/확인: {db_path.parent.absolute()}")

    # 엔진 생성
    try:
        engine = create_engine(db_url)
        print("✓ 데이터베이스 엔진 생성 성공")
    except Exception as e:
        print(f"✗ 엔진 생성 실패: {e}")
        return False

    # 테이블 생성
    try:
        Base.metadata.create_all(bind=engine)
        print("✓ 모든 테이블 생성 완료")
    except Exception as e:
        print(f"✗ 테이블 생성 실패: {e}")
        return False

    # 테이블 확인
    try:
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"\n생성된 테이블 ({len(tables)}개):")
        for table in tables:
            print(f"  - {table}")
    except Exception as e:
        print(f"⚠ 테이블 목록 조회 실패: {e}")

    print("\n" + "=" * 60)
    print("데이터베이스 초기화 완료!")
    print("=" * 60)

    return True

if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1)
