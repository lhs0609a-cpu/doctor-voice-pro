import requests
import sys

backend_ok = False
frontend_ok = False

try:
    r = requests.get('http://localhost:8010/health', timeout=2)
    backend_ok = r.status_code == 200
except:
    pass

try:
    r = requests.get('http://localhost:3001', timeout=2)
    frontend_ok = r.status_code in [200, 304, 404]
except:
    pass

print(f'Backend (8010): {"OK - Connected" if backend_ok else "Not Connected"}')
print(f'Frontend (3001): {"OK - Connected" if frontend_ok else "Not Connected"}')
print()

if backend_ok and frontend_ok:
    print('✓ Both servers are running and connected!')
    sys.exit(0)
else:
    print('✗ One or more servers are not connected')
    sys.exit(1)
