"""
시스템 API - 서버 상태 및 동기화 관련 엔드포인트
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import socket
import os
import json
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timedelta
from app.core.config import settings
from app.db.database import get_db, AsyncSessionLocal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import anthropic
from openai import OpenAI

# Gemini SDK 임포트 (설치되어 있는 경우)
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None

# AI 사용량 모델 임포트
from app.models.ai_usage import AIUsage, AI_PRICING, USD_TO_KRW, calculate_cost, get_estimated_cost_per_request
from app.models import APIKey


# DB에서 API 키 로드하는 함수
async def get_api_key_from_db(provider: str) -> Optional[str]:
    """
    DB에서 특정 provider의 API 키를 조회합니다.
    DB에 키가 없으면 환경변수에서 가져옵니다.
    """
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(APIKey).where(APIKey.provider == provider, APIKey.is_active == True)
            )
            key_record = result.scalar_one_or_none()
            if key_record:
                return key_record.api_key
    except Exception as e:
        print(f"[WARNING] DB에서 API 키 조회 실패: {e}")

    # DB에 없으면 환경변수에서 로드
    if provider == "claude":
        return settings.ANTHROPIC_API_KEY
    elif provider == "gpt":
        return settings.OPENAI_API_KEY
    elif provider == "gemini":
        return settings.GEMINI_API_KEY
    return None

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


@router.get("/claude-api-status")
async def get_claude_api_status():
    """
    Claude API 연결 상태 확인 (DB 또는 환경변수)
    """
    # DB에서 먼저 API 키 조회, 없으면 환경변수에서 조회
    api_key = await get_api_key_from_db("claude")

    if not api_key or api_key == "":
        return {
            "connected": False,
            "error": "API 키가 설정되지 않았습니다",
            "api_key_set": False
        }

    try:
        # Anthropic 클라이언트 생성 및 간단한 API 호출 테스트
        client = anthropic.Anthropic(api_key=api_key)

        # 매우 짧은 메시지로 연결 테스트
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=10,
            messages=[{"role": "user", "content": "test"}]
        )

        return {
            "connected": True,
            "api_key_set": True,
            "api_key_prefix": api_key[:10] + "..." if len(api_key) > 10 else "***",
            "model": "claude-sonnet-4-5-20250929",
            "test_successful": True
        }
    except Exception as e:
        return {
            "connected": False,
            "api_key_set": True,
            "api_key_prefix": api_key[:10] + "..." if len(api_key) > 10 else "***",
            "error": str(e),
            "test_successful": False
        }


@router.get("/gpt-api-status")
async def get_gpt_api_status():
    """
    GPT API 연결 상태 확인 (DB 또는 환경변수)
    """
    # DB에서 먼저 API 키 조회, 없으면 환경변수에서 조회
    api_key = await get_api_key_from_db("gpt")

    if not api_key or api_key == "":
        return {
            "connected": False,
            "error": "API 키가 설정되지 않았습니다",
            "api_key_set": False
        }

    try:
        # OpenAI 클라이언트 생성 및 간단한 API 호출 테스트
        client = OpenAI(api_key=api_key)

        # 매우 짧은 메시지로 연결 테스트
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=10,
            messages=[{"role": "user", "content": "test"}]
        )

        return {
            "connected": True,
            "api_key_set": True,
            "api_key_prefix": api_key[:10] + "..." if len(api_key) > 10 else "***",
            "model": "gpt-4o-mini",
            "test_successful": True
        }
    except Exception as e:
        return {
            "connected": False,
            "api_key_set": True,
            "api_key_prefix": api_key[:10] + "..." if len(api_key) > 10 else "***",
            "error": str(e),
            "test_successful": False
        }


@router.get("/gemini-api-status")
async def get_gemini_api_status():
    """
    Gemini API 연결 상태 확인 (DB 또는 환경변수)
    """
    if not GEMINI_AVAILABLE:
        return {
            "connected": False,
            "error": "google-generativeai 패키지가 설치되지 않았습니다",
            "api_key_set": False,
            "sdk_available": False
        }

    # DB에서 먼저 API 키 조회, 없으면 환경변수에서 조회
    api_key = await get_api_key_from_db("gemini")

    if not api_key or api_key == "":
        return {
            "connected": False,
            "error": "API 키가 설정되지 않았습니다",
            "api_key_set": False,
            "sdk_available": True
        }

    try:
        # Gemini 클라이언트 설정 및 간단한 API 호출 테스트
        genai.configure(api_key=api_key)

        # 안정적인 gemini-2.0-flash 모델로 테스트
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content("test", generation_config=genai.GenerationConfig(max_output_tokens=10))

        return {
            "connected": True,
            "api_key_set": True,
            "api_key_prefix": api_key[:10] + "..." if len(api_key) > 10 else "***",
            "model": "gemini-2.0-flash",
            "test_successful": True,
            "sdk_available": True,
            "available_models": [
                "gemini-2.0-flash",
                "gemini-1.5-pro",
                "gemini-2.0-flash-exp"
            ]
        }
    except Exception as e:
        return {
            "connected": False,
            "api_key_set": True,
            "api_key_prefix": api_key[:10] + "..." if len(api_key) > 10 else "***",
            "error": str(e),
            "test_successful": False,
            "sdk_available": True
        }


@router.get("/ai-pricing")
async def get_ai_pricing():
    """
    AI 모델별 가격 정보 조회
    """
    pricing_info = []
    for model_id, info in AI_PRICING.items():
        # 원고 1건 (1800자) 기준 예상 비용 계산
        estimated = get_estimated_cost_per_request(model_id, 1800)

        pricing_info.append({
            "model_id": model_id,
            "model_name": info["name"],
            "input_price_per_1m": info["input"],
            "output_price_per_1m": info["output"],
            "estimated_cost_per_post_usd": estimated["total_cost_usd"],
            "estimated_cost_per_post_krw": estimated["total_cost_krw"],
            "provider": "claude" if "claude" in model_id else ("gemini" if "gemini" in model_id else "gpt"),
        })

    # 가격순 정렬 (저렴한 것부터)
    pricing_info.sort(key=lambda x: x["estimated_cost_per_post_krw"])

    return {
        "usd_to_krw": USD_TO_KRW,
        "pricing": pricing_info,
        "note": "예상 비용은 1800자 원고 기준입니다. 실제 비용은 프롬프트 길이와 생성 결과에 따라 달라질 수 있습니다."
    }


@router.get("/ai-usage-stats")
async def get_ai_usage_stats(db: AsyncSession = Depends(get_db)):
    """
    전체 AI 사용량 통계 조회
    """
    try:
        # 전체 사용량 집계
        total_result = await db.execute(
            select(
                func.count(AIUsage.id).label("total_requests"),
                func.sum(AIUsage.input_tokens).label("total_input_tokens"),
                func.sum(AIUsage.output_tokens).label("total_output_tokens"),
                func.sum(AIUsage.cost_usd).label("total_cost_usd"),
                func.sum(AIUsage.cost_krw).label("total_cost_krw"),
            )
        )
        total = total_result.first()

        # 모델별 사용량 집계
        model_result = await db.execute(
            select(
                AIUsage.ai_provider,
                AIUsage.ai_model,
                func.count(AIUsage.id).label("request_count"),
                func.sum(AIUsage.input_tokens).label("input_tokens"),
                func.sum(AIUsage.output_tokens).label("output_tokens"),
                func.sum(AIUsage.cost_usd).label("cost_usd"),
                func.sum(AIUsage.cost_krw).label("cost_krw"),
            ).group_by(AIUsage.ai_provider, AIUsage.ai_model)
        )
        by_model = model_result.all()

        # 오늘 사용량
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_result = await db.execute(
            select(
                func.count(AIUsage.id).label("requests"),
                func.sum(AIUsage.cost_krw).label("cost_krw"),
            ).where(AIUsage.created_at >= today_start)
        )
        today = today_result.first()

        # 이번 달 사용량
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_result = await db.execute(
            select(
                func.count(AIUsage.id).label("requests"),
                func.sum(AIUsage.cost_krw).label("cost_krw"),
            ).where(AIUsage.created_at >= month_start)
        )
        month = month_result.first()

        # 최근 10건 사용 기록
        recent_result = await db.execute(
            select(AIUsage).order_by(AIUsage.created_at.desc()).limit(10)
        )
        recent_usage = recent_result.scalars().all()

        return {
            "total": {
                "requests": total.total_requests or 0,
                "input_tokens": total.total_input_tokens or 0,
                "output_tokens": total.total_output_tokens or 0,
                "cost_usd": round(total.total_cost_usd or 0, 4),
                "cost_krw": round(total.total_cost_krw or 0, 0),
            },
            "today": {
                "requests": today.requests or 0,
                "cost_krw": round(today.cost_krw or 0, 0),
            },
            "this_month": {
                "requests": month.requests or 0,
                "cost_krw": round(month.cost_krw or 0, 0),
            },
            "by_model": [
                {
                    "provider": row.ai_provider,
                    "model": row.ai_model,
                    "model_name": AI_PRICING.get(row.ai_model, {}).get("name", row.ai_model),
                    "requests": row.request_count,
                    "input_tokens": row.input_tokens or 0,
                    "output_tokens": row.output_tokens or 0,
                    "cost_usd": round(row.cost_usd or 0, 4),
                    "cost_krw": round(row.cost_krw or 0, 0),
                }
                for row in by_model
            ],
            "recent": [
                {
                    "id": str(usage.id),
                    "provider": usage.ai_provider,
                    "model": usage.ai_model,
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "cost_krw": round(usage.cost_krw, 0),
                    "created_at": usage.created_at.isoformat(),
                }
                for usage in recent_usage
            ],
            "usd_to_krw": USD_TO_KRW,
        }
    except Exception as e:
        # 테이블이 없거나 에러 발생 시
        return {
            "total": {"requests": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0, "cost_krw": 0},
            "today": {"requests": 0, "cost_krw": 0},
            "this_month": {"requests": 0, "cost_krw": 0},
            "by_model": [],
            "recent": [],
            "usd_to_krw": USD_TO_KRW,
            "error": str(e),
        }
