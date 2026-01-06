"""공공데이터 리드 수집 API"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import List, Optional
from datetime import datetime
import uuid

from ..models.user import User
from ..models.public_leads import (
    PublicLead,
    PublicLeadDB,
    LeadSearchRequest,
    LeadSearchResponse,
    LeadStats,
    LeadStatus,
    SIDO_LIST,
    CATEGORY_LIST
)
from ..services.public_data_service import public_data_service
from .deps import get_current_user
from ..db.database import get_db

router = APIRouter(prefix="/public-leads", tags=["공공데이터 리드"])


@router.get("/regions")
async def get_regions():
    """시도/시군구 목록 조회"""
    sigungu_map = {
        "서울특별시": ["강남구", "강동구", "강북구", "강서구", "관악구", "광진구", "구로구", "금천구",
                   "노원구", "도봉구", "동대문구", "동작구", "마포구", "서대문구", "서초구", "성동구",
                   "성북구", "송파구", "양천구", "영등포구", "용산구", "은평구", "종로구", "중구", "중랑구"],
        "부산광역시": ["강서구", "금정구", "기장군", "남구", "동구", "동래구", "부산진구", "북구",
                   "사상구", "사하구", "서구", "수영구", "연제구", "영도구", "중구", "해운대구"],
        "대구광역시": ["남구", "달서구", "달성군", "동구", "북구", "서구", "수성구", "중구"],
        "인천광역시": ["강화군", "계양구", "남동구", "동구", "미추홀구", "부평구", "서구", "연수구", "옹진군", "중구"],
        "광주광역시": ["광산구", "남구", "동구", "북구", "서구"],
        "대전광역시": ["대덕구", "동구", "서구", "유성구", "중구"],
        "울산광역시": ["남구", "동구", "북구", "울주군", "중구"],
        "세종특별자치시": ["세종시"],
        "경기도": ["가평군", "고양시", "과천시", "광명시", "광주시", "구리시", "군포시", "김포시",
                 "남양주시", "동두천시", "부천시", "성남시", "수원시", "시흥시", "안산시", "안성시",
                 "안양시", "양주시", "양평군", "여주시", "연천군", "오산시", "용인시", "의왕시",
                 "의정부시", "이천시", "파주시", "평택시", "포천시", "하남시", "화성시"],
        "강원도": ["강릉시", "고성군", "동해시", "삼척시", "속초시", "양구군", "양양군", "영월군",
                 "원주시", "인제군", "정선군", "철원군", "춘천시", "태백시", "평창군", "홍천군", "화천군", "횡성군"],
        "충청북도": ["괴산군", "단양군", "보은군", "영동군", "옥천군", "음성군", "제천시", "증평군", "진천군", "청주시", "충주시"],
        "충청남도": ["계룡시", "공주시", "금산군", "논산시", "당진시", "보령시", "부여군", "서산시",
                   "서천군", "아산시", "예산군", "천안시", "청양군", "태안군", "홍성군"],
        "전라북도": ["고창군", "군산시", "김제시", "남원시", "무주군", "부안군", "순창군", "완주군",
                   "익산시", "임실군", "장수군", "전주시", "정읍시", "진안군"],
        "전라남도": ["강진군", "고흥군", "곡성군", "광양시", "구례군", "나주시", "담양군", "목포시",
                   "무안군", "보성군", "순천시", "신안군", "여수시", "영광군", "영암군", "완도군",
                   "장성군", "장흥군", "진도군", "함평군", "해남군", "화순군"],
        "경상북도": ["경산시", "경주시", "고령군", "구미시", "군위군", "김천시", "문경시", "봉화군",
                   "상주시", "성주군", "안동시", "영덕군", "영양군", "영주시", "영천시", "예천군",
                   "울릉군", "울진군", "의성군", "청도군", "청송군", "칠곡군", "포항시"],
        "경상남도": ["거제시", "거창군", "고성군", "김해시", "남해군", "밀양시", "사천시", "산청군",
                   "양산시", "의령군", "진주시", "창녕군", "창원시", "통영시", "하동군", "함안군", "함양군", "합천군"],
        "제주특별자치도": ["서귀포시", "제주시"],
    }

    return {
        "sido_list": SIDO_LIST,
        "sigungu_map": sigungu_map,
        "categories": CATEGORY_LIST
    }


@router.post("/search", response_model=LeadSearchResponse)
async def search_leads(
    request: LeadSearchRequest,
    current_user: User = Depends(get_current_user)
):
    """리드 검색 및 수집"""
    try:
        leads = await public_data_service.search_stores_by_region(
            sido=request.sido,
            sigungu=request.sigungu,
            dong=request.dong,
            category=request.category,
            keyword=request.keyword,
            limit=request.limit
        )

        # 사용자 ID 설정
        for lead in leads:
            lead.user_id = str(current_user.id)
            lead.id = str(uuid.uuid4())

        return LeadSearchResponse(
            success=True,
            total=len(leads),
            leads=leads,
            message=f"{len(leads)}개의 리드를 수집했습니다."
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save")
async def save_leads(
    leads: List[PublicLead],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """수집된 리드 저장"""
    try:
        saved_count = 0
        duplicates = 0

        for lead in leads:
            # 중복 체크 (상호명 + 주소)
            stmt = select(PublicLeadDB).where(
                and_(
                    PublicLeadDB.user_id == str(current_user.id),
                    PublicLeadDB.business_name == lead.business_name,
                    PublicLeadDB.address == lead.address
                )
            )
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()

            if not existing:
                new_lead = PublicLeadDB(
                    id=str(uuid.uuid4()),
                    user_id=str(current_user.id),
                    business_name=lead.business_name,
                    category=lead.category,
                    sub_category=lead.sub_category,
                    address=lead.address,
                    road_address=lead.road_address,
                    sido=lead.sido,
                    sigungu=lead.sigungu,
                    dong=lead.dong,
                    phone=lead.phone,
                    email=lead.email,
                    website=lead.website,
                    business_number=lead.business_number,
                    owner_name=lead.owner_name,
                    open_date=lead.open_date,
                    status="new",
                    score=lead.score or 50,
                    notes=lead.notes,
                    tags=lead.tags or [],
                    source=lead.source or "public_data",
                    collected_at=datetime.utcnow(),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                db.add(new_lead)
                saved_count += 1
            else:
                duplicates += 1

        await db.commit()

        return {
            "success": True,
            "saved": saved_count,
            "duplicates": duplicates,
            "message": f"{saved_count}개 저장, {duplicates}개 중복"
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_leads(
    status: Optional[str] = None,
    category: Optional[str] = None,
    sido: Optional[str] = None,
    sigungu: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """저장된 리드 목록 조회"""
    try:
        # 기본 쿼리
        conditions = [PublicLeadDB.user_id == str(current_user.id)]

        if status:
            conditions.append(PublicLeadDB.status == status)
        if category:
            conditions.append(PublicLeadDB.category == category)
        if sido:
            conditions.append(PublicLeadDB.sido == sido)
        if sigungu:
            conditions.append(PublicLeadDB.sigungu == sigungu)
        if search:
            conditions.append(
                or_(
                    PublicLeadDB.business_name.ilike(f"%{search}%"),
                    PublicLeadDB.address.ilike(f"%{search}%"),
                    PublicLeadDB.phone.ilike(f"%{search}%")
                )
            )

        # 총 개수 조회
        count_stmt = select(func.count()).select_from(PublicLeadDB).where(and_(*conditions))
        total_result = await db.execute(count_stmt)
        total = total_result.scalar()

        # 리드 조회
        stmt = select(PublicLeadDB).where(and_(*conditions)).order_by(
            PublicLeadDB.created_at.desc()
        ).offset(skip).limit(limit)
        result = await db.execute(stmt)
        leads = result.scalars().all()

        return {
            "success": True,
            "total": total,
            "leads": [lead.to_dict() for lead in leads],
            "skip": skip,
            "limit": limit
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_lead_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """리드 통계 조회"""
    try:
        user_id = str(current_user.id)

        # 총 개수
        total_stmt = select(func.count()).select_from(PublicLeadDB).where(
            PublicLeadDB.user_id == user_id
        )
        total_result = await db.execute(total_stmt)
        total = total_result.scalar()

        # 상태별 통계
        by_status = {}
        for status in LeadStatus:
            status_stmt = select(func.count()).select_from(PublicLeadDB).where(
                and_(
                    PublicLeadDB.user_id == user_id,
                    PublicLeadDB.status == status.value
                )
            )
            status_result = await db.execute(status_stmt)
            by_status[status.value] = status_result.scalar()

        # 업종별 통계
        category_stmt = select(
            PublicLeadDB.category,
            func.count().label('count')
        ).where(PublicLeadDB.user_id == user_id).group_by(
            PublicLeadDB.category
        ).order_by(func.count().desc()).limit(5)
        category_result = await db.execute(category_stmt)
        by_category = {row.category: row.count for row in category_result}

        # 지역별 통계
        region_stmt = select(
            PublicLeadDB.sigungu,
            func.count().label('count')
        ).where(PublicLeadDB.user_id == user_id).group_by(
            PublicLeadDB.sigungu
        ).order_by(func.count().desc()).limit(5)
        region_result = await db.execute(region_stmt)
        by_region = {row.sigungu: row.count for row in region_result}

        # 오늘 수집된 리드
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        recent_stmt = select(func.count()).select_from(PublicLeadDB).where(
            and_(
                PublicLeadDB.user_id == user_id,
                PublicLeadDB.created_at >= today_start
            )
        )
        recent_result = await db.execute(recent_stmt)
        recent_collected = recent_result.scalar()

        # 오늘 연락한 리드
        contacted_stmt = select(func.count()).select_from(PublicLeadDB).where(
            and_(
                PublicLeadDB.user_id == user_id,
                PublicLeadDB.status == "contacted",
                PublicLeadDB.last_contacted_at >= today_start
            )
        )
        contacted_result = await db.execute(contacted_stmt)
        contacted_today = contacted_result.scalar()

        return LeadStats(
            total=total,
            by_status=by_status,
            by_category=by_category,
            by_region=by_region,
            recent_collected=recent_collected,
            contacted_today=contacted_today
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{lead_id}")
async def update_lead(
    lead_id: str,
    update_data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """리드 정보 수정"""
    try:
        stmt = select(PublicLeadDB).where(
            and_(
                PublicLeadDB.id == lead_id,
                PublicLeadDB.user_id == str(current_user.id)
            )
        )
        result = await db.execute(stmt)
        lead = result.scalar_one_or_none()

        if not lead:
            raise HTTPException(status_code=404, detail="리드를 찾을 수 없습니다")

        # 허용된 필드만 업데이트
        allowed_fields = ["status", "notes", "tags", "email", "phone", "score"]
        for key, value in update_data.items():
            if key in allowed_fields:
                setattr(lead, key, value)

        lead.updated_at = datetime.utcnow()

        if update_data.get("status") == "contacted":
            lead.last_contacted_at = datetime.utcnow()

        await db.commit()

        return {"success": True, "message": "리드가 수정되었습니다"}

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{lead_id}")
async def delete_lead(
    lead_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """리드 삭제"""
    try:
        stmt = select(PublicLeadDB).where(
            and_(
                PublicLeadDB.id == lead_id,
                PublicLeadDB.user_id == str(current_user.id)
            )
        )
        result = await db.execute(stmt)
        lead = result.scalar_one_or_none()

        if not lead:
            raise HTTPException(status_code=404, detail="리드를 찾을 수 없습니다")

        await db.delete(lead)
        await db.commit()

        return {"success": True, "message": "리드가 삭제되었습니다"}

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{lead_id}/enrich")
async def enrich_lead(
    lead_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """리드 정보 보강 (웹사이트, 이메일 추출)"""
    try:
        stmt = select(PublicLeadDB).where(
            and_(
                PublicLeadDB.id == lead_id,
                PublicLeadDB.user_id == str(current_user.id)
            )
        )
        result = await db.execute(stmt)
        lead = result.scalar_one_or_none()

        if not lead:
            raise HTTPException(status_code=404, detail="리드를 찾을 수 없습니다")

        # Pydantic 모델로 변환
        lead_model = PublicLead(**lead.to_dict())
        enriched_lead = await public_data_service.enrich_lead(lead_model)

        # 업데이트
        if enriched_lead.email:
            lead.email = enriched_lead.email
        if enriched_lead.website:
            lead.website = enriched_lead.website
        if enriched_lead.score:
            lead.score = enriched_lead.score
        lead.updated_at = datetime.utcnow()

        await db.commit()

        return {
            "success": True,
            "lead": lead.to_dict(),
            "message": "리드 정보가 보강되었습니다"
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export-to-outreach")
async def export_to_outreach(
    lead_ids: List[str],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """선택한 리드를 이메일 영업 시스템으로 내보내기"""
    try:
        from ..models.blog_outreach import NaverBlog, BlogContact

        exported = 0
        for lead_id in lead_ids:
            # 리드 조회
            stmt = select(PublicLeadDB).where(
                and_(
                    PublicLeadDB.id == lead_id,
                    PublicLeadDB.user_id == str(current_user.id)
                )
            )
            result = await db.execute(stmt)
            lead = result.scalar_one_or_none()

            if lead and lead.email:
                # 이메일 영업 블로그로 변환
                blog = NaverBlog(
                    id=str(uuid.uuid4()),
                    user_id=str(current_user.id),
                    blog_id=f"public_{lead.id[:8]}",
                    blog_url=lead.website or "",
                    blog_name=lead.business_name,
                    category="health",
                    lead_score=lead.score or 50,
                    lead_grade="C" if (lead.score or 50) < 60 else "B" if (lead.score or 50) < 80 else "A",
                    status="contact_found",
                    has_contact=True,
                    notes=f"공공데이터에서 수집: {lead.address}",
                    collected_at=datetime.utcnow(),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                db.add(blog)

                # 연락처 생성
                contact = BlogContact(
                    id=str(uuid.uuid4()),
                    blog_id=blog.id,
                    email=lead.email,
                    phone=lead.phone,
                    source="profile",
                    is_primary=True,
                    is_verified=False,
                    extracted_at=datetime.utcnow(),
                    created_at=datetime.utcnow(),
                )
                db.add(contact)

                # 원본 리드 상태 업데이트
                lead.status = "contacted"
                lead.updated_at = datetime.utcnow()

                exported += 1

        await db.commit()

        return {
            "success": True,
            "exported": exported,
            "total": len(lead_ids),
            "message": f"{exported}개의 리드가 이메일 영업으로 내보내졌습니다"
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{lead_id}/extract-email")
async def extract_email_for_lead(
    lead_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """단일 리드의 이메일 추출"""
    try:
        from ..services.lead_email_extractor import lead_email_extractor

        stmt = select(PublicLeadDB).where(
            and_(
                PublicLeadDB.id == lead_id,
                PublicLeadDB.user_id == str(current_user.id)
            )
        )
        result = await db.execute(stmt)
        lead = result.scalar_one_or_none()

        if not lead:
            raise HTTPException(status_code=404, detail="리드를 찾을 수 없습니다")

        # 이메일 추출
        extraction_result = await lead_email_extractor.extract_email_for_lead(
            business_name=lead.business_name or "",
            address=lead.address or "",
            website=lead.website,
            phone=lead.phone
        )

        # 결과 저장
        if extraction_result.get("email"):
            lead.email = extraction_result["email"]
            lead.score = min((lead.score or 50) + 30, 100)

        if extraction_result.get("website") and not lead.website:
            lead.website = extraction_result["website"]

        if extraction_result.get("phone") and not lead.phone:
            lead.phone = extraction_result["phone"]

        lead.updated_at = datetime.utcnow()

        await db.commit()

        return {
            "success": True,
            "email": extraction_result.get("email"),
            "all_emails": extraction_result.get("all_emails", []),
            "website": extraction_result.get("website"),
            "phone": extraction_result.get("phone"),
            "extraction_methods": extraction_result.get("extraction_methods", []),
            "message": f"이메일 추출 완료: {extraction_result.get('email') or '이메일을 찾을 수 없습니다'}"
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-extract-emails")
async def batch_extract_emails(
    lead_ids: List[str],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """여러 리드의 이메일 일괄 추출"""
    try:
        from ..services.lead_email_extractor import lead_email_extractor

        # 리드 조회
        stmt = select(PublicLeadDB).where(
            and_(
                PublicLeadDB.id.in_(lead_ids),
                PublicLeadDB.user_id == str(current_user.id)
            )
        )
        result = await db.execute(stmt)
        leads = result.scalars().all()

        if not leads:
            return {
                "success": False,
                "message": "추출할 리드가 없습니다"
            }

        # 배치 추출 준비
        lead_data = [
            {
                "id": lead.id,
                "business_name": lead.business_name or "",
                "address": lead.address or "",
                "website": lead.website,
                "phone": lead.phone
            }
            for lead in leads
        ]

        # 배치 추출
        results = await lead_email_extractor.batch_extract(lead_data)

        # 결과 저장
        extracted_count = 0
        lead_map = {lead.id: lead for lead in leads}

        for extraction_result in results:
            if extraction_result.get("success") and extraction_result.get("email"):
                lead_id = extraction_result["lead_id"]
                lead = lead_map.get(lead_id)

                if lead:
                    lead.email = extraction_result["email"]
                    lead.score = min((lead.score or 50) + 30, 100)

                    if extraction_result.get("website"):
                        lead.website = extraction_result["website"]

                    lead.updated_at = datetime.utcnow()
                    extracted_count += 1

        await db.commit()

        return {
            "success": True,
            "total": len(lead_ids),
            "extracted": extracted_count,
            "results": results,
            "message": f"{len(lead_ids)}개 중 {extracted_count}개의 이메일을 추출했습니다"
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
