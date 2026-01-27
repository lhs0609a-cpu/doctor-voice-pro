"""
Demo API - 온보딩 체험용 API (인증 불필요)
P0 버그 수정: 온보딩 Demo 실제 API 연동
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any

from app.services.medical_law_checker import medical_law_checker

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


class DemoTransformRequest(BaseModel):
    """데모 변환 요청"""
    text: str


class DemoTransformResponse(BaseModel):
    """데모 변환 응답"""
    original_text: str
    transformed_text: str
    medical_law_check: Dict[str, Any]
    violations_fixed: List[Dict[str, str]]
    stats: Dict[str, Any]


# 샘플 변환 결과 (AI API 호출 없이 데모용으로 제공)
SAMPLE_TRANSFORMATIONS = {
    "default": """피부과 전문의로서 10년간 수천 건의 시술 경험을 바탕으로 말씀드립니다.

최근 도입한 프락셀 레이저는 표피 손상을 최소화하면서 진피층까지 열에너지를 전달하는 방식입니다. 개인차가 있지만, 많은 분들이 3-5회 시술 후 눈에 띄는 개선을 경험하고 계십니다.

시술 전 충분한 상담을 통해 피부 상태를 정확히 파악하고, 현실적인 기대 효과를 안내해 드립니다. 모든 시술에는 개인차가 있으며, 저희는 정직한 상담을 약속드립니다."""
}


@router.post("/transform", response_model=DemoTransformResponse)
async def demo_transform(request: DemoTransformRequest):
    """
    온보딩 데모용 텍스트 변환 API

    - 인증 불필요 (공개 API)
    - 의료법 검증 실제 수행
    - 변환 결과는 샘플 데이터 (AI API 비용 절감)

    Returns:
        변환 전/후 텍스트, 의료법 검증 결과, 수정된 표현 목록
    """
    if not request.text or len(request.text.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="텍스트는 최소 10자 이상이어야 합니다."
        )

    original_text = request.text.strip()

    # 실제 의료법 검증 수행
    law_check_result = medical_law_checker.check(original_text)

    # 자동 수정 수행
    fixed_text, changes = medical_law_checker.auto_fix(original_text)

    # 위반 사항이 있으면 수정된 텍스트 사용, 없으면 샘플 변환 사용
    if changes:
        transformed_text = fixed_text
    else:
        # 위반이 없으면 기본 샘플 변환 텍스트 사용
        transformed_text = SAMPLE_TRANSFORMATIONS["default"]

    # 수정된 표현 목록 정리
    violations_fixed = [
        {
            "original": change["original"],
            "replaced": change["replaced"],
            "category": change["category"]
        }
        for change in changes
    ]

    # 통계 정보
    stats = {
        "persuasion_score": 87,  # 데모용 고정값
        "compliance_score": medical_law_checker.get_compliance_score(transformed_text),
        "original_length": len(original_text),
        "transformed_length": len(transformed_text),
        "violations_count": len(law_check_result["violations"]),
        "warnings_count": len(law_check_result["warnings"]),
        "skipped_count": len(law_check_result.get("skipped", [])),
        "estimated_time_saved_minutes": 45
    }

    return DemoTransformResponse(
        original_text=original_text,
        transformed_text=transformed_text,
        medical_law_check={
            "is_compliant": law_check_result["is_compliant"],
            "violations": law_check_result["violations"],
            "warnings": law_check_result["warnings"],
            "skipped": law_check_result.get("skipped", []),
            "disclaimer": law_check_result["disclaimer"]
        },
        violations_fixed=violations_fixed,
        stats=stats
    )


@router.post("/medical-law-check")
async def demo_medical_law_check(request: DemoTransformRequest):
    """
    온보딩 데모용 의료법 검증 API

    - 인증 불필요 (공개 API)
    - 실제 의료법 검증 수행

    Returns:
        의료법 검증 결과
    """
    if not request.text or len(request.text.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="텍스트는 최소 10자 이상이어야 합니다."
        )

    # 실제 의료법 검증 수행
    result = medical_law_checker.check(request.text.strip())
    compliance_score = medical_law_checker.get_compliance_score(request.text.strip())

    return {
        "is_compliant": result["is_compliant"],
        "compliance_score": compliance_score,
        "violations": result["violations"],
        "warnings": result["warnings"],
        "skipped": result.get("skipped", []),
        "total_issues": result["total_issues"],
        "disclaimer": result["disclaimer"]
    }
