# 자동 배포 설정 가이드

## 🚀 Fly.io 자동 배포 설정

GitHub에 푸시할 때마다 자동으로 Fly.io에 배포되도록 설정하는 방법입니다.

### 1단계: Fly.io API 토큰 발급

터미널에서 다음 명령어를 실행하세요:

```bash
flyctl auth token
```

출력된 토큰을 복사해두세요. (예: `FlyV1 fm1_...`)

### 2단계: GitHub Secrets에 토큰 추가

1. GitHub 저장소로 이동: https://github.com/lhs0609a-cpu/doctor-voice-pro
2. **Settings** 탭 클릭
3. 왼쪽 메뉴에서 **Secrets and variables** → **Actions** 클릭
4. **New repository secret** 버튼 클릭
5. 다음 정보 입력:
   - **Name**: `FLY_API_TOKEN`
   - **Value**: 1단계에서 복사한 토큰 붙여넣기
6. **Add secret** 버튼 클릭

### 3단계: GitHub에 푸시

```bash
# 변경사항 커밋
git add .github/workflows/fly-deploy.yml
git add DEPLOYMENT.md
git commit -m "Add Fly.io auto-deployment workflow"

# GitHub에 푸시
git push origin main
```

### 4단계: 배포 확인

1. GitHub 저장소의 **Actions** 탭에서 배포 진행 상황 확인
2. 성공하면 `backend/` 폴더 변경 시마다 자동 배포됨

## 📝 작동 방식

- `backend/` 폴더 또는 workflow 파일이 변경되면 자동 배포
- `main` 브랜치에 푸시할 때만 작동
- Fly.io 원격 빌더 사용 (`--remote-only`)

## 🔍 배포 로그 확인

```bash
# Fly.io 배포 로그 확인
flyctl logs -a doctor-voice-pro-backend

# 앱 상태 확인
flyctl status -a doctor-voice-pro-backend
```

## 🎯 현재 배포 상태

### 백엔드 (Fly.io)
- **URL**: https://doctor-voice-pro-backend.fly.dev
- **자동 배포**: ✅ 설정 완료 (설정 후)
- **배포 조건**: `backend/` 폴더 변경 + `main` 브랜치 푸시

### 프론트엔드 (Vercel)
- **자동 배포**: ✅ 이미 설정됨
- **배포 조건**: `main` 브랜치 푸시

## ⚠️ 참고사항

- Fly.io 무료 티어 제한: 월 $5 크레딧
- 빌드 시간: 약 2-5분
- 배포 실패 시 GitHub Actions 탭에서 로그 확인
