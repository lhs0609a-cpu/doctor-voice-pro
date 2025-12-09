"""
시스템 API - 서버 상태 및 동기화 관련 엔드포인트
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import socket
import os
import json
from pathlib import Path
from typing import Optional

router = APIRouter()


class ServerInfo(BaseModel):
    backend_port: int
    frontend_port: Optional[int] = None
    backend_url: str
    frontend_url: Optional[str] = None
    status: str


class PortCheckRequest(BaseModel):
    port: int


class PortCheckResponse(BaseModel):
    port: int
    available: bool


@router.get("/server-info", response_model=ServerInfo)
async def get_server_info():
    """
    현재 서버 정보 조회
    """
    # 현재 프로세스의 포트 번호 확인 (환경 변수나 설정 파일에서)
    backend_port = int(os.getenv("PORT", 8010))

    # server_info.json 파일에서 포트 정보 로드
    project_root = Path(__file__).parent.parent.parent.parent
    info_file = project_root / "server_info.json"

    frontend_port = None
    if info_file.exists():
        try:
            info = json.loads(info_file.read_text(encoding='utf-8'))
            backend_port = info.get("backend_port", backend_port)
            frontend_port = info.get("frontend_port")
        except:
            pass

    backend_url = f"http://localhost:{backend_port}"
    frontend_url = f"http://localhost:{frontend_port}" if frontend_port else None

    return ServerInfo(
        backend_port=backend_port,
        frontend_port=frontend_port,
        backend_url=backend_url,
        frontend_url=frontend_url,
        status="running"
    )


@router.post("/check-port", response_model=PortCheckResponse)
async def check_port(request: PortCheckRequest):
    """
    특정 포트의 사용 가능 여부 확인
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('0.0.0.0', request.port))
            available = True
    except OSError:
        available = False

    return PortCheckResponse(
        port=request.port,
        available=available
    )


@router.get("/available-ports")
async def get_available_ports(start_port: int = 8000, count: int = 10):
    """
    사용 가능한 포트 목록 조회
    """
    available_ports = []

    for port in range(start_port, start_port + 100):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('0.0.0.0', port))
                available_ports.append(port)
                if len(available_ports) >= count:
                    break
        except OSError:
            continue

    return {
        "available_ports": available_ports,
        "count": len(available_ports)
    }


@router.get("/connection-status")
async def get_connection_status():
    """
    백엔드-프론트엔드 연결 상태 확인
    """
    project_root = Path(__file__).parent.parent.parent.parent
    info_file = project_root / "server_info.json"

    if info_file.exists():
        try:
            info = json.loads(info_file.read_text(encoding='utf-8'))
            return {
                "connected": True,
                "backend_port": info.get("backend_port"),
                "frontend_port": info.get("frontend_port"),
                "timestamp": info.get("timestamp")
            }
        except:
            return {"connected": False, "error": "Failed to read server info"}

    return {"connected": False, "error": "Server info not found"}
