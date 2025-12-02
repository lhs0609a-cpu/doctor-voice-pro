"""
간단한 목(Mock) 백엔드 서버
의존성 없이 Python 기본 라이브러리만 사용
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from urllib.parse import urlparse, parse_qs

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
            except:
                pass

        # Register endpoint
        if parsed_path.path == '/api/v1/auth/register':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                self._set_headers(201)
                response = {
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
                    "created_at": "2025-01-01T00:00:00"
                }
                self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))
                return
            except:
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
Status: Running

Note: This is a test mock server.
For full AI features, run the complete backend.

You can check server connection status at:
http://localhost:3001

Press Ctrl+C to stop the server.
===============================================================
""")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n서버를 중지합니다...")
        httpd.server_close()


if __name__ == '__main__':
    run_mock_server(5000)
