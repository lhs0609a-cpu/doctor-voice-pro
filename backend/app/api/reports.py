"""
마케팅 리포트 API
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from datetime import date
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.report import ReportType, ReportFormat, ReportStatus
from app.services.report_service import report_service

router = APIRouter()


# ==================== Schemas ====================

class ReportGenerateRequest(BaseModel):
    report_type: ReportType
    period_start: str = Field(..., description="YYYY-MM-DD")
    period_end: str = Field(..., description="YYYY-MM-DD")
    title: Optional[str] = None


class MonthlyReportRequest(BaseModel):
    year: int = Field(..., ge=2020, le=2100)
    month: int = Field(..., ge=1, le=12)


class ReportSubscriptionRequest(BaseModel):
    auto_monthly: Optional[bool] = None
    auto_weekly: Optional[bool] = None
    email_enabled: Optional[bool] = None
    email_recipients: Optional[List[str]] = None
    preferred_format: Optional[ReportFormat] = None


class ReportResponse(BaseModel):
    id: str
    report_type: str
    title: str
    period_start: str
    period_end: str
    status: str
    generated_at: Optional[str]
    pdf_url: Optional[str]
    excel_url: Optional[str]
    email_sent: bool
    created_at: str

    class Config:
        from_attributes = True


class ReportDetailResponse(ReportResponse):
    report_data: Optional[dict]


class ReportSubscriptionResponse(BaseModel):
    auto_monthly: bool
    auto_weekly: bool
    email_enabled: bool
    email_recipients: Optional[List[str]]
    preferred_format: str


# ==================== Helper Functions ====================

def parse_date(date_str: str) -> date:
    """YYYY-MM-DD 문자열을 date 객체로 변환"""
    parts = date_str.split("-")
    return date(int(parts[0]), int(parts[1]), int(parts[2]))


def report_to_response(report) -> dict:
    """MarketingReport를 응답 딕셔너리로 변환"""
    return {
        "id": str(report.id),
        "report_type": report.report_type.value,
        "title": report.title,
        "period_start": report.period_start.isoformat(),
        "period_end": report.period_end.isoformat(),
        "status": report.status.value,
        "generated_at": report.generated_at.isoformat() if report.generated_at else None,
        "pdf_url": report.pdf_url,
        "excel_url": report.excel_url,
        "email_sent": report.email_sent,
        "created_at": report.created_at.isoformat(),
    }


def report_to_detail_response(report) -> dict:
    """MarketingReport를 상세 응답 딕셔너리로 변환"""
    response = report_to_response(report)
    response["report_data"] = report.report_data
    return response


# ==================== Endpoints ====================

@router.post("/generate", response_model=ReportDetailResponse)
async def generate_report(
    request: ReportGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    리포트 생성
    """
    try:
        period_start = parse_date(request.period_start)
        period_end = parse_date(request.period_end)

        if period_start > period_end:
            raise HTTPException(status_code=400, detail="시작일은 종료일보다 이전이어야 합니다")

        report = await report_service.generate_report(
            db=db,
            user_id=str(current_user.id),
            report_type=request.report_type,
            period_start=period_start,
            period_end=period_end,
            title=request.title,
        )

        return report_to_detail_response(report)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/monthly", response_model=ReportDetailResponse)
async def generate_monthly_report(
    request: MonthlyReportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    월간 리포트 생성
    """
    try:
        report = await report_service.generate_monthly_report(
            db=db,
            user_id=str(current_user.id),
            year=request.year,
            month=request.month,
        )

        return report_to_detail_response(report)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/weekly", response_model=ReportDetailResponse)
async def generate_weekly_report(
    week_start: Optional[str] = Query(None, description="YYYY-MM-DD (주 시작일)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    주간 리포트 생성
    """
    try:
        week_start_date = parse_date(week_start) if week_start else None

        report = await report_service.generate_weekly_report(
            db=db,
            user_id=str(current_user.id),
            week_start=week_start_date,
        )

        return report_to_detail_response(report)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[ReportResponse])
async def get_reports(
    report_type: Optional[ReportType] = None,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    리포트 목록 조회
    """
    reports = await report_service.get_reports(
        db=db,
        user_id=str(current_user.id),
        report_type=report_type,
        limit=limit,
        offset=offset,
    )

    return [report_to_response(r) for r in reports]


@router.get("/subscription", response_model=ReportSubscriptionResponse)
async def get_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    리포트 자동 생성 구독 설정 조회
    """
    subscription = await report_service.get_subscription(
        db=db,
        user_id=str(current_user.id),
    )

    if not subscription:
        return {
            "auto_monthly": False,
            "auto_weekly": False,
            "email_enabled": False,
            "email_recipients": None,
            "preferred_format": ReportFormat.PDF.value,
        }

    return {
        "auto_monthly": subscription.auto_monthly,
        "auto_weekly": subscription.auto_weekly,
        "email_enabled": subscription.email_enabled,
        "email_recipients": subscription.email_recipients,
        "preferred_format": subscription.preferred_format.value,
    }


@router.put("/subscription", response_model=ReportSubscriptionResponse)
async def update_subscription(
    request: ReportSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    리포트 자동 생성 구독 설정 업데이트
    """
    subscription = await report_service.update_subscription(
        db=db,
        user_id=str(current_user.id),
        auto_monthly=request.auto_monthly,
        auto_weekly=request.auto_weekly,
        email_enabled=request.email_enabled,
        email_recipients=request.email_recipients,
        preferred_format=request.preferred_format,
    )

    return {
        "auto_monthly": subscription.auto_monthly,
        "auto_weekly": subscription.auto_weekly,
        "email_enabled": subscription.email_enabled,
        "email_recipients": subscription.email_recipients,
        "preferred_format": subscription.preferred_format.value,
    }


@router.get("/{report_id}", response_model=ReportDetailResponse)
async def get_report(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    리포트 상세 조회
    """
    report = await report_service.get_report(
        db=db,
        report_id=report_id,
        user_id=str(current_user.id),
    )

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return report_to_detail_response(report)


@router.get("/{report_id}/download/excel")
async def download_excel(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Excel 파일 다운로드
    """
    excel_bytes = await report_service.export_to_excel(
        db=db,
        report_id=report_id,
        user_id=str(current_user.id),
    )

    if not excel_bytes:
        raise HTTPException(status_code=404, detail="Report not found or Excel generation failed")

    report = await report_service.get_report(db, report_id, str(current_user.id))
    filename = f"marketing_report_{report.period_start}_{report.period_end}.xlsx"

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.delete("/{report_id}")
async def delete_report(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    리포트 삭제
    """
    success = await report_service.delete_report(
        db=db,
        report_id=report_id,
        user_id=str(current_user.id),
    )

    if not success:
        raise HTTPException(status_code=404, detail="Report not found")

    return {"message": "Report deleted successfully"}
