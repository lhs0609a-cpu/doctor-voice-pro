import socket

def is_port_free(port):
    """Check if a port is available"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        return result != 0
    except:
        return False

# Common ports to check
ports_to_check = [5000, 5001, 5002, 5003, 8080, 8081, 8082, 8083, 9000, 9001, 9002, 9003]

print("Available ports:")
free_ports = []
for port in ports_to_check:
    if is_port_free(port):
        free_ports.append(port)
        print(f"  OK {port}")
    else:
        print(f"  NO {port} (in use)")

if len(free_ports) >= 2:
    print(f"\nRecommended ports:")
    print(f"  Backend: {free_ports[0]}")
    print(f"  Frontend: {free_ports[1]}")
