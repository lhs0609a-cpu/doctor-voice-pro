"""공공데이터 리드 수집 API"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from datetime import datetime
import json

from ..models.user import User
from ..models.public_leads import (
    PublicLead,
    LeadSearchRequest,
    LeadSearchResponse,
    LeadStats,
    LeadStatus,
    SIDO_LIST,
    CATEGORY_LIST
)
from ..services.public_data_service import public_data_service
from ..core.auth import get_current_user
from ..core.database import get_db

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
        "경기도": ["가평군", "고양시", "과천시", "광명시", "광주시", "구리시", "군포시", "김포시",
                 "남양주시", "동두천시", "부천시", "성남시", "수원시", "시흥시", "안산시", "안성시",
                 "안양시", "양주시", "양평군", "여주시", "연천군", "오산시", "용인시", "의왕시",
                 "의정부시", "이천시", "파주시", "평택시", "포천시", "하남시", "화성시"],
        "인천광역시": ["강화군", "계양구", "남동구", "동구", "미추홀구", "부평구", "서구", "연수구", "옹진군", "중구"],
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
            lead.user_id = current_user.id

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
    db=Depends(get_db)
):
    """수집된 리드 저장"""
    try:
        saved_count = 0
        collection = db["public_leads"]

        for lead in leads:
            lead.user_id = current_user.id
            lead.created_at = datetime.now()
            lead.updated_at = datetime.now()

            # 중복 체크 (상호명 + 주소)
            existing = await collection.find_one({
                "user_id": current_user.id,
                "business_name": lead.business_name,
                "address": lead.address
            })

            if not existing:
                await collection.insert_one(lead.model_dump())
                saved_count += 1

        return {
            "success": True,
            "saved": saved_count,
            "duplicates": len(leads) - saved_count,
            "message": f"{saved_count}개 저장, {len(leads) - saved_count}개 중복"
        }

    except Exception as e:
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
    db=Depends(get_db)
):
    """저장된 리드 목록 조회"""
    try:
        collection = db["public_leads"]

        query = {"user_id": current_user.id}

        if status:
            query["status"] = status
        if category:
            query["category"] = category
        if sido:
            query["sido"] = sido
        if sigungu:
            query["sigungu"] = sigungu
        if search:
            query["$or"] = [
                {"business_name": {"$regex": search, "$options": "i"}},
                {"address": {"$regex": search, "$options": "i"}},
                {"phone": {"$regex": search, "$options": "i"}}
            ]

        total = await collection.count_documents(query)
        cursor = collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        leads = await cursor.to_list(length=limit)

        # ObjectId를 문자열로 변환
        for lead in leads:
            lead["id"] = str(lead.pop("_id"))

        return {
            "success": True,
            "total": total,
            "leads": leads,
            "skip": skip,
            "limit": limit
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_lead_stats(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """리드 통계 조회"""
    try:
        collection = db["public_leads"]
        base_query = {"user_id": current_user.id}

        total = await collection.count_documents(base_query)

        # 상태별 통계
        by_status = {}
        for status in LeadStatus:
            count = await collection.count_documents({**base_query, "status": status.value})
            by_status[status.value] = count

        # 업종별 통계 (상위 5개)
        pipeline = [
            {"$match": base_query},
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]
        category_cursor = collection.aggregate(pipeline)
        by_category = {doc["_id"]: doc["count"] async for doc in category_cursor}

        # 지역별 통계 (상위 5개)
        pipeline = [
            {"$match": base_query},
            {"$group": {"_id": "$sigungu", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]
        region_cursor = collection.aggregate(pipeline)
        by_region = {doc["_id"]: doc["count"] async for doc in region_cursor}

        return LeadStats(
            total=total,
            by_status=by_status,
            by_category=by_category,
            by_region=by_region,
            recent_collected=await collection.count_documents({
                **base_query,
                "created_at": {"$gte": datetime.now().replace(hour=0, minute=0, second=0)}
            }),
            contacted_today=await collection.count_documents({
                **base_query,
                "status": "contacted",
                "last_contacted_at": {"$gte": datetime.now().replace(hour=0, minute=0, second=0)}
            })
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{lead_id}")
async def update_lead(
    lead_id: str,
    update_data: dict,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """리드 정보 수정"""
    try:
        from bson import ObjectId

        collection = db["public_leads"]

        # 허용된 필드만 업데이트
        allowed_fields = ["status", "notes", "tags", "email", "phone", "score"]
        update_dict = {k: v for k, v in update_data.items() if k in allowed_fields}
        update_dict["updated_at"] = datetime.now()

        if "status" in update_dict and update_dict["status"] == "contacted":
            update_dict["last_contacted_at"] = datetime.now()

        result = await collection.update_one(
            {"_id": ObjectId(lead_id), "user_id": current_user.id},
            {"$set": update_dict}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="리드를 찾을 수 없습니다")

        return {"success": True, "message": "리드가 수정되었습니다"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{lead_id}")
async def delete_lead(
    lead_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """리드 삭제"""
    try:
        from bson import ObjectId

        collection = db["public_leads"]
        result = await collection.delete_one({
            "_id": ObjectId(lead_id),
            "user_id": current_user.id
        })

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="리드를 찾을 수 없습니다")

        return {"success": True, "message": "리드가 삭제되었습니다"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{lead_id}/enrich")
async def enrich_lead(
    lead_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """리드 정보 보강 (웹사이트, 이메일 추출)"""
    try:
        from bson import ObjectId

        collection = db["public_leads"]
        lead_doc = await collection.find_one({
            "_id": ObjectId(lead_id),
            "user_id": current_user.id
        })

        if not lead_doc:
            raise HTTPException(status_code=404, detail="리드를 찾을 수 없습니다")

        lead = PublicLead(**{**lead_doc, "id": str(lead_doc["_id"])})
        enriched_lead = await public_data_service.enrich_lead(lead)

        await collection.update_one(
            {"_id": ObjectId(lead_id)},
            {"$set": {
                "email": enriched_lead.email,
                "website": enriched_lead.website,
                "score": enriched_lead.score,
                "updated_at": datetime.now()
            }}
        )

        return {
            "success": True,
            "lead": enriched_lead.model_dump(),
            "message": "리드 정보가 보강되었습니다"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export-to-outreach")
async def export_to_outreach(
    lead_ids: List[str],
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """선택한 리드를 이메일 영업 시스템으로 내보내기"""
    try:
        from bson import ObjectId

        leads_collection = db["public_leads"]
        outreach_collection = db["naver_blog_leads"]

        exported = 0
        for lead_id in lead_ids:
            lead_doc = await leads_collection.find_one({
                "_id": ObjectId(lead_id),
                "user_id": current_user.id
            })

            if lead_doc and lead_doc.get("email"):
                # 이메일 영업 리드로 변환
                outreach_lead = {
                    "user_id": current_user.id,
                    "blog_name": lead_doc["business_name"],
                    "blog_url": lead_doc.get("website", ""),
                    "niche": lead_doc["category"],
                    "email": lead_doc["email"],
                    "phone": lead_doc.get("phone"),
                    "status": "new",
                    "score": lead_doc.get("score", 50),
                    "source": "public_data",
                    "notes": f"공공데이터에서 수집: {lead_doc['address']}",
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                }

                await outreach_collection.insert_one(outreach_lead)

                # 원본 리드 상태 업데이트
                await leads_collection.update_one(
                    {"_id": ObjectId(lead_id)},
                    {"$set": {"status": "contacted", "updated_at": datetime.now()}}
                )

                exported += 1

        return {
            "success": True,
            "exported": exported,
            "total": len(lead_ids),
            "message": f"{exported}개의 리드가 이메일 영업으로 내보내졌습니다"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{lead_id}/extract-email")
async def extract_email_for_lead(
    lead_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """단일 리드의 이메일 추출"""
    try:
        from bson import ObjectId
        from ..services.lead_email_extractor import lead_email_extractor

        collection = db["public_leads"]
        lead_doc = await collection.find_one({
            "_id": ObjectId(lead_id),
            "user_id": current_user.id
        })

        if not lead_doc:
            raise HTTPException(status_code=404, detail="리드를 찾을 수 없습니다")

        # 이메일 추출
        result = await lead_email_extractor.extract_email_for_lead(
            business_name=lead_doc.get("business_name", ""),
            address=lead_doc.get("address", ""),
            website=lead_doc.get("website"),
            phone=lead_doc.get("phone")
        )

        # 결과 저장
        update_data = {"updated_at": datetime.now()}

        if result.get("email"):
            update_data["email"] = result["email"]
            update_data["score"] = min((lead_doc.get("score", 50) + 30), 100)

        if result.get("website") and not lead_doc.get("website"):
            update_data["website"] = result["website"]

        if result.get("phone") and not lead_doc.get("phone"):
            update_data["phone"] = result["phone"]

        await collection.update_one(
            {"_id": ObjectId(lead_id)},
            {"$set": update_data}
        )

        return {
            "success": True,
            "email": result.get("email"),
            "all_emails": result.get("all_emails", []),
            "website": result.get("website"),
            "phone": result.get("phone"),
            "extraction_methods": result.get("extraction_methods", []),
            "message": f"이메일 추출 완료: {result.get('email') or '이메일을 찾을 수 없습니다'}"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-extract-emails")
async def batch_extract_emails(
    lead_ids: List[str],
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """여러 리드의 이메일 일괄 추출"""
    try:
        from bson import ObjectId
        from ..services.lead_email_extractor import lead_email_extractor

        collection = db["public_leads"]

        # 리드 조회
        leads = []
        for lead_id in lead_ids:
            lead_doc = await collection.find_one({
                "_id": ObjectId(lead_id),
                "user_id": current_user.id
            })
            if lead_doc:
                leads.append({
                    "id": str(lead_doc["_id"]),
                    "business_name": lead_doc.get("business_name", ""),
                    "address": lead_doc.get("address", ""),
                    "website": lead_doc.get("website"),
                    "phone": lead_doc.get("phone")
                })

        if not leads:
            return {
                "success": False,
                "message": "추출할 리드가 없습니다"
            }

        # 배치 추출
        results = await lead_email_extractor.batch_extract(leads)

        # 결과 저장
        extracted_count = 0
        for result in results:
            if result.get("success") and result.get("email"):
                lead_id = result["lead_id"]

                update_data = {
                    "email": result["email"],
                    "updated_at": datetime.now()
                }

                if result.get("website"):
                    update_data["website"] = result["website"]

                # 스코어 증가
                lead_doc = await collection.find_one({"_id": ObjectId(lead_id)})
                if lead_doc:
                    update_data["score"] = min((lead_doc.get("score", 50) + 30), 100)

                await collection.update_one(
                    {"_id": ObjectId(lead_id)},
                    {"$set": update_data}
                )

                extracted_count += 1

        return {
            "success": True,
            "total": len(lead_ids),
            "extracted": extracted_count,
            "results": results,
            "message": f"{len(lead_ids)}개 중 {extracted_count}개의 이메일을 추출했습니다"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
