"""공공데이터 API 서비스"""
import os
import aiohttp
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
import urllib.parse
import json
import re
from ..models.public_leads import PublicLead, LeadSearchRequest, LeadStatus


class PublicDataService:
    """공공데이터 포털 API 서비스"""

    def __init__(self):
        self.api_key = os.getenv("PUBLIC_DATA_API_KEY", "")
        self.base_url = "http://apis.data.go.kr"

        # 소상공인시장진흥공단 상가업소 API
        self.store_api_url = f"{self.base_url}/B553077/api/open/sdsc2/storeListInDong"

        # 국세청 사업자등록 상태조회 API
        self.bizno_api_url = f"{self.base_url}/B090041/openapi/service/SbsttInfoService/getBmanInfo"

    async def search_stores_by_region(
        self,
        sido: str,
        sigungu: Optional[str] = None,
        dong: Optional[str] = None,
        category: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 100
    ) -> List[PublicLead]:
        """지역별 상가업소 검색"""
        leads = []

        # API 키가 없으면 시뮬레이션 데이터 반환
        if not self.api_key:
            return await self._generate_simulation_data(
                sido, sigungu, dong, category, keyword, limit
            )

        try:
            params = {
                "serviceKey": self.api_key,
                "pageNo": "1",
                "numOfRows": str(min(limit, 1000)),
                "divId": "ctprvnCd",
                "key": self._get_sido_code(sido),
                "type": "json"
            }

            if category:
                params["indsLclsCd"] = self._get_category_code(category)

            async with aiohttp.ClientSession() as session:
                async with session.get(self.store_api_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        items = data.get("body", {}).get("items", [])

                        for item in items[:limit]:
                            lead = self._parse_store_item(item, sido, sigungu)
                            if lead:
                                # 키워드 필터링
                                if keyword and keyword not in lead.business_name:
                                    continue
                                # 시군구 필터링
                                if sigungu and sigungu not in lead.address:
                                    continue
                                # 동 필터링
                                if dong and dong not in lead.address:
                                    continue
                                leads.append(lead)

        except Exception as e:
            print(f"API 호출 오류: {e}")
            # 오류 시 시뮬레이션 데이터 반환
            return await self._generate_simulation_data(
                sido, sigungu, dong, category, keyword, limit
            )

        return leads[:limit]

    def _parse_store_item(self, item: dict, sido: str, sigungu: Optional[str]) -> Optional[PublicLead]:
        """API 응답 항목을 PublicLead로 변환"""
        try:
            return PublicLead(
                id=str(item.get("bizesId", "")),
                business_name=item.get("bizesNm", ""),
                category=item.get("indsLclsNm", "기타"),
                sub_category=item.get("indsMclsNm", ""),
                address=item.get("lnoAdr", ""),
                road_address=item.get("rdnmAdr", ""),
                sido=sido,
                sigungu=item.get("signguNm", sigungu or ""),
                dong=item.get("adongNm", ""),
                phone=self._clean_phone(item.get("telNo", "")),
                open_date=item.get("opnSvcNm", ""),
                source="소상공인시장진흥공단",
                collected_at=datetime.now(),
                created_at=datetime.now()
            )
        except Exception:
            return None

    def _clean_phone(self, phone: str) -> Optional[str]:
        """전화번호 정제"""
        if not phone:
            return None
        # 숫자와 하이픈만 남기기
        cleaned = re.sub(r'[^\d-]', '', phone)
        if len(cleaned) >= 9:
            return cleaned
        return None

    def _get_sido_code(self, sido: str) -> str:
        """시도명을 코드로 변환"""
        codes = {
            "서울특별시": "11", "부산광역시": "26", "대구광역시": "27",
            "인천광역시": "28", "광주광역시": "29", "대전광역시": "30",
            "울산광역시": "31", "세종특별자치시": "36", "경기도": "41",
            "강원도": "42", "충청북도": "43", "충청남도": "44",
            "전라북도": "45", "전라남도": "46", "경상북도": "47",
            "경상남도": "48", "제주특별자치도": "50"
        }
        return codes.get(sido, "11")

    def _get_category_code(self, category: str) -> str:
        """업종명을 코드로 변환"""
        codes = {
            "음식점": "I", "의료": "Q", "교육": "P",
            "서비스": "S", "소매": "G", "부동산": "L",
            "반려동물": "R", "자동차": "H"
        }
        return codes.get(category, "")

    async def _generate_simulation_data(
        self,
        sido: str,
        sigungu: Optional[str],
        dong: Optional[str],
        category: Optional[str],
        keyword: Optional[str],
        limit: int
    ) -> List[PublicLead]:
        """시뮬레이션 데이터 생성 (API 키 없을 때)"""
        import random

        # 업종별 상호명 템플릿
        business_templates = {
            "음식점": ["맛있는 {}", "{} 식당", "{}네 밥집", "{} 분식", "황금 {}", "{} 한정식"],
            "카페": ["{} 카페", "카페 {}", "{} 커피", "{}다방", "{} 로스터리"],
            "병원": ["{} 병원", "{}의원", "{} 클리닉", "{} 메디컬"],
            "치과": ["{} 치과", "{}치과의원", "{} 덴탈", "{} 스마일치과"],
            "미용실": ["{} 헤어", "헤어샵 {}", "{} 뷰티", "{} 미용실"],
            "학원": ["{} 학원", "{}교육", "{} 아카데미", "{} 영어"],
            "헬스장": ["{} 휘트니스", "{} 짐", "{} 헬스", "{} 스포츠"],
            "부동산": ["{} 공인중개사", "{} 부동산", "{}랜드"],
        }

        names = ["행복", "사랑", "우리", "미소", "참", "좋은", "새벽", "하늘", "푸른", "정성"]
        sigungu_list = ["강남구", "서초구", "송파구", "마포구", "용산구", "종로구", "중구", "영등포구"]
        dong_list = ["역삼동", "삼성동", "논현동", "청담동", "신사동", "압구정동", "대치동"]

        target_category = category or random.choice(list(business_templates.keys()))
        templates = business_templates.get(target_category, ["{} 상점"])

        leads = []
        for i in range(limit):
            name = random.choice(names)
            template = random.choice(templates)
            business_name = template.format(name)

            if keyword and keyword not in business_name:
                business_name = f"{keyword} {business_name}"

            target_sigungu = sigungu or random.choice(sigungu_list)
            target_dong = dong or random.choice(dong_list)

            # 가상 전화번호 생성
            phone = f"02-{random.randint(1000,9999)}-{random.randint(1000,9999)}"

            lead = PublicLead(
                id=f"sim_{i+1}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                business_name=business_name,
                category=target_category,
                address=f"{sido} {target_sigungu} {target_dong} {random.randint(1,500)}번지",
                road_address=f"{sido} {target_sigungu} {target_dong}로 {random.randint(1,200)}",
                sido=sido,
                sigungu=target_sigungu,
                dong=target_dong,
                phone=phone,
                owner_name=f"{random.choice(['김', '이', '박', '최', '정'])}대표",
                source="시뮬레이션 (API 키 필요)",
                score=random.randint(30, 90),
                collected_at=datetime.now(),
                created_at=datetime.now()
            )
            leads.append(lead)

        return leads

    async def enrich_lead(self, lead: PublicLead) -> PublicLead:
        """리드 정보 보강 (웹사이트, 이메일 추출 등)"""
        # 네이버 플레이스 검색으로 추가 정보 수집
        try:
            search_query = f"{lead.business_name} {lead.sigungu}"
            # 여기서 네이버 검색 API나 크롤링으로 웹사이트, 이메일 추출 가능
            # 현재는 기본 구현만

            # 스코어 계산
            score = 50
            if lead.phone:
                score += 20
            if lead.email:
                score += 30
            if lead.website:
                score += 10

            lead.score = min(score, 100)

        except Exception as e:
            print(f"리드 보강 오류: {e}")

        return lead

    async def check_business_status(self, business_number: str) -> dict:
        """사업자등록 상태 조회"""
        if not self.api_key or not business_number:
            return {"status": "unknown", "message": "조회 불가"}

        try:
            params = {
                "serviceKey": self.api_key,
                "bno": business_number.replace("-", ""),
                "type": "json"
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(self.bizno_api_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("body", {"status": "unknown"})

        except Exception as e:
            print(f"사업자 조회 오류: {e}")

        return {"status": "unknown", "message": "조회 실패"}


# 싱글톤 인스턴스
public_data_service = PublicDataService()
