import socket
import json

def is_port_available(port):
    """Check if a port is available"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', port))
            return True
    except OSError:
        return False

def find_available_ports(start_port=8000, count=2):
    """Find available ports starting from start_port"""
    available_ports = []
    port = start_port

    while len(available_ports) < count:
        if is_port_available(port):
            available_ports.append(port)
        port += 1

        # Safety limit
        if port > start_port + 1000:
            break

    return available_ports

# Find available ports
backend_candidates = find_available_ports(8000, 3)
frontend_candidates = find_available_ports(3000, 3)

result = {
    "backend_port": backend_candidates[0] if backend_candidates else 8010,
    "frontend_port": frontend_candidates[0] if frontend_candidates else 3000,
    "backend_candidates": backend_candidates,
    "frontend_candidates": frontend_candidates
}

print(json.dumps(result, indent=2))

# Save to file
with open('port_config.json', 'w') as f:
    json.dump(result, f, indent=2)

print(f"\n✓ Backend Port: {result['backend_port']}")
print(f"✓ Frontend Port: {result['frontend_port']}")
print(f"\nConfig saved to port_config.json")
