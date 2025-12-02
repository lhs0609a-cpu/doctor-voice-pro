"""
WebSocket API Router
실시간 진행상황 업데이트
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Set
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Active WebSocket connections
# Format: {user_id: {connection_id: websocket}}
active_connections: Dict[str, Dict[str, WebSocket]] = {}


class ConnectionManager:
    """WebSocket 연결 관리자"""

    def __init__(self):
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str, connection_id: str):
        """WebSocket 연결"""
        await websocket.accept()

        if user_id not in self.active_connections:
            self.active_connections[user_id] = {}

        self.active_connections[user_id][connection_id] = websocket
        logger.info(f"WebSocket connected: user={user_id}, connection={connection_id}")

    def disconnect(self, user_id: str, connection_id: str):
        """WebSocket 연결 해제"""
        if user_id in self.active_connections:
            if connection_id in self.active_connections[user_id]:
                del self.active_connections[user_id][connection_id]
                logger.info(f"WebSocket disconnected: user={user_id}, connection={connection_id}")

            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_message(self, user_id: str, message: dict):
        """특정 사용자에게 메시지 전송"""
        if user_id in self.active_connections:
            disconnected = []

            for connection_id, websocket in self.active_connections[user_id].items():
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to send message to {user_id}/{connection_id}: {e}")
                    disconnected.append(connection_id)

            # Remove disconnected connections
            for connection_id in disconnected:
                self.disconnect(user_id, connection_id)

    async def send_progress(
        self,
        user_id: str,
        task_id: str,
        stage: str,
        progress: int,
        message: str,
        data: dict = None
    ):
        """진행상황 업데이트 전송"""
        await self.send_message(user_id, {
            "type": "progress",
            "task_id": task_id,
            "stage": stage,
            "progress": progress,
            "message": message,
            "data": data or {}
        })

    async def send_completion(
        self,
        user_id: str,
        task_id: str,
        success: bool,
        message: str,
        data: dict = None
    ):
        """작업 완료 전송"""
        await self.send_message(user_id, {
            "type": "completion",
            "task_id": task_id,
            "success": success,
            "message": message,
            "data": data or {}
        })

    async def send_error(
        self,
        user_id: str,
        task_id: str,
        error: str
    ):
        """에러 전송"""
        await self.send_message(user_id, {
            "type": "error",
            "task_id": task_id,
            "error": error
        })


# Global connection manager
manager = ConnectionManager()


@router.websocket("/ws/{user_id}/{connection_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    connection_id: str
):
    """
    WebSocket 엔드포인트

    실시간 진행상황을 받기 위한 WebSocket 연결
    """
    await manager.connect(websocket, user_id, connection_id)

    try:
        while True:
            # Keep connection alive and handle ping/pong
            data = await websocket.receive_text()

            # Handle ping
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        manager.disconnect(user_id, connection_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(user_id, connection_id)


# Export manager for use in other modules
def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager"""
    return manager
