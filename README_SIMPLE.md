# 닥터보이스 프로 v2.2.0

## 🚀 원클릭 시작 (가장 쉬운 방법)

### 1️⃣ 더블클릭으로 실행
```
ONE_CLICK_INSTALL_AND_RUN.bat
```

**끝!** 모든 것이 자동으로 설치되고 실행됩니다.

---

## 📋 필수 요구사항

이 프로그램을 실행하기 전에 다음이 설치되어 있어야 합니다:

### ✅ Python 3.10 이상
- 다운로드: https://www.python.org/downloads/
- 설치 시 "Add Python to PATH" 체크 필수!

### ✅ Node.js 16 이상
- 다운로드: https://nodejs.org/
- LTS 버전 권장

---

## 🎯 처음 사용하는 경우

### 방법 1: 원클릭 실행 (권장) ⭐
1. `ONE_CLICK_INSTALL_AND_RUN.bat` 더블클릭
2. 자동 설치 및 실행 (3-5분 소요)
3. 완료!

### 방법 2: 수동 설치
```batch
# 1. 백엔드 설치
cd backend
pip install -r requirements.txt
python -m alembic upgrade head

# 2. 프론트엔드 설치
cd ../frontend
npm install

# 3. 실행
cd ..
run_connected.bat
```

---

## 🔧 이미 설치된 경우

바로 실행하세요:
```
run_connected.bat
```

---

## 🌐 접속 주소

서버가 시작되면:
- **프론트엔드**: http://localhost:3000
- **백엔드 API**: http://localhost:8010
- **API 문서**: http://localhost:8010/docs

---

## ❗ 문제 발생 시

### 백엔드 시작 실패
```batch
cd backend
pip install --upgrade sqlalchemy anthropic
```

### 포트 충돌
- `run_connected.bat`은 자동으로 다른 포트를 찾습니다
- 또는 충돌하는 프로그램을 종료하세요

### 자세한 문제 해결
- `QUICK_FIX.md` 참조
- `START_HERE.md` 참조

---

## 📁 주요 파일

| 파일 | 설명 |
|------|------|
| `ONE_CLICK_INSTALL_AND_RUN.bat` | 원클릭 설치 및 실행 ⭐ |
| `run_connected.bat` | 빠른 실행 (이미 설치된 경우) |
| `QUICK_FIX.md` | 문제 해결 가이드 |
| `START_HERE.md` | 상세 사용 설명서 |

---

## 🔐 API 키 설정 (선택사항)

AI 기능을 사용하려면:

1. `backend/.env` 파일 생성
2. 다음 내용 입력:
```env
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
```

---

## 🎨 주요 기능

- ✅ AI 음성 톤 변환 (GPT-4)
- ✅ 템플릿 관리
- ✅ 변환 히스토리
- ✅ 사용량 통계
- ✅ 자동 연결 관리
- ✅ 포트 자동 탐색

---

## 🆘 도움말

문제가 해결되지 않으면:
1. `logs/` 폴더 확인
2. `error_reports/` 폴더 확인
3. `QUICK_FIX.md` 참조

---

**버전**: v2.2.0
**업데이트**: 2025-10-31
**한글 완벽 지원** 🇰🇷
