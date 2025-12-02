"""
간단한 목(Mock) 백엔드 서버
의존성 없이 Python 기본 라이브러리만 사용
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta

# Mock 사용자 데이터베이스
MOCK_USERS = [
    {
        "id": "user-uuid-1",
        "email": "test1@example.com",
        "name": "김의사",
        "hospital_name": "서울정형외과",
        "specialty": "정형외과",
        "subscription_tier": "free",
        "is_active": True,
        "is_approved": False,  # 승인 대기
        "is_admin": False,
        "subscription_start_date": None,
        "subscription_end_date": None,
        "created_at": "2025-01-28T10:00:00"
    },
    {
        "id": "user-uuid-2",
        "email": "test2@example.com",
        "name": "이원장",
        "hospital_name": "부산치과",
        "specialty": "치과",
        "subscription_tier": "free",
        "is_active": True,
        "is_approved": False,  # 승인 대기
        "is_admin": False,
        "subscription_start_date": None,
        "subscription_end_date": None,
        "created_at": "2025-01-29T09:00:00"
    },
    {
        "id": "user-uuid-3",
        "email": "approved@example.com",
        "name": "박박사",
        "hospital_name": "대전내과",
        "specialty": "내과",
        "subscription_tier": "basic",
        "is_active": True,
        "is_approved": True,  # 이미 승인됨
        "is_admin": False,
        "subscription_start_date": "2025-01-20T00:00:00",
        "subscription_end_date": "2025-02-20T00:00:00",
        "created_at": "2025-01-20T15:00:00"
    }
]

class MockAPIHandler(BaseHTTPRequestHandler):
    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self._set_headers(200)

    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)

        # Health check endpoint
        if parsed_path.path == '/health':
            self._set_headers(200)
            response = {"status": "healthy", "message": "목 서버가 실행 중입니다"}
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))
            return

        # Root endpoint
        if parsed_path.path == '/':
            self._set_headers(200)
            response = {
                "name": "DoctorVoice Pro Mock API",
                "version": "1.0.0-mock",
                "status": "running",
                "docs": "/docs (실제 서버에서 사용 가능)",
                "message": "프론트엔드 테스트용 목 서버입니다"
            }
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))
            return

        # Auth - Get current user (me)
        if parsed_path.path == '/api/v1/auth/me':
            # Extract token from Authorization header
            auth_header = self.headers.get('Authorization', '')
            if not auth_header or not auth_header.startswith('Bearer '):
                self._set_headers(401)
                response = {"detail": "인증이 필요합니다"}
                self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))
                return

            token = auth_header.replace('Bearer ', '')

            # Mock admin token check
            if token == 'mock_admin_token_12345':
                self._set_headers(200)
                user = {
                    "id": "admin-uuid-1234",
                    "email": "admin@doctorvoice.com",
                    "name": "관리자",
                    "hospital_name": "닥터보이스 프로 관리팀",
                    "specialty": "관리",
                    "subscription_tier": "enterprise",
                    "is_active": True,
                    "is_approved": True,
                    "is_admin": True,
                    "subscription_start_date": None,
                    "subscription_end_date": None,
                    "created_at": "2025-01-01T00:00:00"
                }
                self.wfile.write(json.dumps(user, ensure_ascii=False).encode('utf-8'))
                return
            else:
                self._set_headers(401)
                response = {"detail": "유효하지 않은 토큰입니다"}
                self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))
                return

        # Posts - Get posts list
        if parsed_path.path == '/api/v1/posts/':
            # Mock empty posts list
            self._set_headers(200)
            response = {
                "posts": [],
                "total": 0,
                "page": 1,
                "page_size": 10
            }
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))
            return

        # Admin - Get users list
        if parsed_path.path == '/api/v1/admin/users':
            # Filter by approval status if requested
            is_approved_param = query_params.get('is_approved', [None])[0]

            filtered_users = MOCK_USERS.copy()
            if is_approved_param is not None:
                is_approved = is_approved_param.lower() == 'true'
                filtered_users = [u for u in filtered_users if u['is_approved'] == is_approved]

            self._set_headers(200)
            self.wfile.write(json.dumps(filtered_users, ensure_ascii=False).encode('utf-8'))
            return

        # Default response
        self._set_headers(404)
        response = {"detail": "Not found", "message": "목 서버입니다. 실제 백엔드를 실행하세요."}
        self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))

    def do_POST(self):
        """Handle POST requests"""
        parsed_path = urlparse(self.path)

        # Login endpoint
        if parsed_path.path == '/api/v1/auth/login':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                email = data.get('email', '')
                password = data.get('password', '')

                # Mock admin login
                if email == 'admin@doctorvoice.com' and password == 'admin123!@#':
                    self._set_headers(200)
                    response = {
                        "access_token": "mock_admin_token_12345",
                        "refresh_token": "mock_refresh_token_12345",
                        "token_type": "bearer",
                        "user": {
                            "id": "admin-uuid-1234",
                            "email": "admin@doctorvoice.com",
                            "name": "관리자",
                            "hospital_name": "닥터보이스 프로 관리팀",
                            "specialty": "관리",
                            "subscription_tier": "enterprise",
                            "is_active": True,
                            "is_approved": True,
                            "is_admin": True,
                            "subscription_start_date": None,
                            "subscription_end_date": None,
                            "created_at": "2025-01-01T00:00:00"
                        }
                    }
                    self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))
                    return
                else:
                    self._set_headers(401)
                    response = {"detail": "이메일 또는 비밀번호가 올바르지 않습니다"}
                    self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))
                    return
            except Exception as e:
                print(f"Error processing login: {e}")
                pass

        # Register endpoint
        if parsed_path.path == '/api/v1/auth/register':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                new_user = {
                    "id": "user-uuid-" + data.get('email', '').split('@')[0],
                    "email": data.get('email', ''),
                    "name": data.get('name'),
                    "hospital_name": data.get('hospital_name'),
                    "specialty": data.get('specialty'),
                    "subscription_tier": "free",
                    "is_active": True,
                    "is_approved": False,
                    "is_admin": False,
                    "subscription_start_date": None,
                    "subscription_end_date": None,
                    "created_at": datetime.now().isoformat()
                }
                MOCK_USERS.append(new_user)
                self._set_headers(201)
                self.wfile.write(json.dumps(new_user, ensure_ascii=False).encode('utf-8'))
                return
            except Exception as e:
                print(f"Error processing registration: {e}")
                pass

        # Admin - Approve user
        if parsed_path.path == '/api/v1/admin/users/approve':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                user_id = data.get('user_id')
                is_approved = data.get('is_approved', True)

                # Find and update user
                for user in MOCK_USERS:
                    if user['id'] == user_id:
                        user['is_approved'] = is_approved
                        self._set_headers(200)
                        self.wfile.write(json.dumps(user, ensure_ascii=False).encode('utf-8'))
                        return

                self._set_headers(404)
                self.wfile.write(json.dumps({"detail": "사용자를 찾을 수 없습니다"}, ensure_ascii=False).encode('utf-8'))
                return
            except Exception as e:
                print(f"Error processing approval: {e}")
                pass

        # Admin - Set subscription
        if parsed_path.path == '/api/v1/admin/users/subscription':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                user_id = data.get('user_id')
                start_date = data.get('subscription_start_date')
                end_date = data.get('subscription_end_date')

                # Find and update user
                for user in MOCK_USERS:
                    if user['id'] == user_id:
                        if start_date:
                            user['subscription_start_date'] = start_date
                        if end_date:
                            user['subscription_end_date'] = end_date
                        self._set_headers(200)
                        self.wfile.write(json.dumps(user, ensure_ascii=False).encode('utf-8'))
                        return

                self._set_headers(404)
                self.wfile.write(json.dumps({"detail": "사용자를 찾을 수 없습니다"}, ensure_ascii=False).encode('utf-8'))
                return
            except Exception as e:
                print(f"Error processing subscription: {e}")
                pass

        # Posts - Create post
        if parsed_path.path == '/api/v1/posts/':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                # Try utf-8 first, then latin-1 as fallback
                try:
                    decoded_data = post_data.decode('utf-8')
                except UnicodeDecodeError:
                    decoded_data = post_data.decode('latin-1')
                data = json.loads(decoded_data)

                # Mock post creation
                mock_post = {
                    "id": "post-" + str(hash(data.get('original_content', '')))[1:10],
                    "title": "AI가 생성한 블로그 제목",
                    "original_content": data.get('original_content', ''),
                    "generated_content": f"[AI 생성 내용]\n\n{data.get('original_content', '')}\n\n이것은 목 서버에서 생성된 샘플 내용입니다. 실제 AI 생성 기능을 사용하려면 백엔드 서버를 실행하세요.",
                    "persuasion_score": 75.5,
                    "persuasion_level": data.get('persuasion_level', 4),
                    "framework": data.get('framework', 'AIDA'),
                    "target_length": data.get('target_length', 1500),
                    "status": "draft",
                    "hashtags": ["#의료정보", "#건강", "#병원", "#의사"],
                    "seo_keywords": ["의료", "건강", "치료", "예방", "관리"],
                    "medical_law_check": {
                        "is_compliant": True,
                        "total_issues": 0,
                        "flagged_expressions": []
                    },
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }

                self._set_headers(201)
                self.wfile.write(json.dumps(mock_post, ensure_ascii=False).encode('utf-8'))
                return
            except Exception as e:
                print(f"Error creating post: {e}")
                pass

        # Default POST response
        self._set_headers(200)
        response = {
            "message": "목 서버입니다",
            "detail": "실제 기능을 사용하려면 전체 백엔드를 실행하세요"
        }
        self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))

    def log_message(self, format, *args):
        """Custom log format"""
        print(f"[Mock Server] {self.address_string()} - {format % args}")


def run_mock_server(port=8000):
    """목 서버 실행"""
    server_address = ('', port)
    httpd = HTTPServer(server_address, MockAPIHandler)

    print(f"""
===============================================================
    DoctorVoice Pro - Mock Backend Server Running
===============================================================

Server Address: http://localhost:{port}
Health Check: http://localhost:{port}/health
Login API: http://localhost:{port}/api/v1/auth/login
Status: Running

Note: This is a test mock server with admin login support.
Admin credentials: admin@doctorvoice.com / admin123!@#

Press Ctrl+C to stop the server.
===============================================================
""")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n서버를 중지합니다...")
        httpd.server_close()


if __name__ == '__main__':
    run_mock_server(8010)
