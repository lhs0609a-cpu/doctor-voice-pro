# 관리자 계정 정보

## 관리자 계정

**이메일**: `admin@doctorvoice.com`
**비밀번호**: `admin123!@#`

⚠️ **보안 경고**: 운영 환경에서는 반드시 비밀번호를 변경하세요!

---

## 관리자 계정 생성 방법

### 방법 1: 스크립트 사용 (데이터베이스가 실행 중일 때)

1. PostgreSQL과 Redis가 실행 중인지 확인:
   ```bash
   docker-compose up -d db redis
   ```

2. 백엔드 의존성 설치:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. 관리자 계정 생성 스크립트 실행:
   ```bash
   python create_admin.py
   ```

### 방법 2: 수동으로 데이터베이스에 추가

1. PostgreSQL에 접속:
   ```bash
   docker exec -it doctorvoice-db psql -U doctorvoice -d doctorvoice
   ```

2. SQL 실행:
   ```sql
   -- 비밀번호 해시 생성 (Python에서 실행)
   -- from app.core.security import get_password_hash
   -- get_password_hash('admin123!@#')

   INSERT INTO users (
       id,
       email,
       hashed_password,
       name,
       hospital_name,
       specialty,
       subscription_tier,
       is_active,
       is_verified,
       is_approved,
       is_admin,
       created_at,
       updated_at
   ) VALUES (
       gen_random_uuid(),
       'admin@doctorvoice.com',
       '$2b$12$[해시된_비밀번호]',  -- 실제 해시 값으로 변경 필요
       '관리자',
       '닥터보이스 프로 관리팀',
       '관리',
       'enterprise',
       true,
       true,
       true,
       true,
       NOW(),
       NOW()
   );
   ```

### 방법 3: 기존 사용자를 관리자로 승격

기존 사용자 계정이 있다면:

```sql
UPDATE users
SET
    is_admin = true,
    is_approved = true,
    is_active = true
WHERE email = '기존이메일@example.com';
```

---

## 로그인 방법

1. 브라우저에서 http://localhost:3003/login 접속
2. **"관리자로 로그인하기"** 버튼 클릭 (자동으로 관리자 계정 정보가 입력되고 로그인됨)
3. 또는 수동으로 이메일과 비밀번호를 입력

---

## 관리자 기능

로그인 후 사용 가능한 관리자 기능:

- `/admin` - 관리자 페이지
  - 사용자 목록 조회
  - 회원가입 승인/거부
  - 사용 기간 설정
  - 사용자 삭제

---

## 현재 서버 상태

- **프론트엔드**: http://localhost:3003
- **백엔드**: http://localhost:8004 (Mock 서버)
  - Mock 서버는 실제 데이터베이스 없이 실행되는 테스트용 서버입니다
  - 실제 관리자 기능을 사용하려면 전체 백엔드와 데이터베이스를 실행해야 합니다

---

## 전체 백엔드 실행 (PostgreSQL + 실제 API)

```bash
# 1. 데이터베이스 실행
docker-compose up -d db redis

# 2. 백엔드 실행 (다른 터미널에서)
cd backend
pip install -r requirements.txt
python create_admin.py  # 관리자 계정 생성
uvicorn app.main:app --host 0.0.0.0 --port 8004 --reload

# 3. 프론트엔드는 이미 실행 중 (http://localhost:3003)
```
