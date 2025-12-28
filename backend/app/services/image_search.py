"""
Image Search Service
무료 이미지 API를 통한 자동 이미지 검색
"""
import httpx
from typing import List, Dict, Optional
import os


class ImageSearchService:
    """
    무료 이미지 검색 서비스 (Unsplash/Pexels)
    """

    def __init__(self):
        # Unsplash API Key (환경변수에서 가져오기)
        self.unsplash_access_key = os.getenv("UNSPLASH_ACCESS_KEY", "")

        # Pexels API Key (대체용)
        self.pexels_api_key = os.getenv("PEXELS_API_KEY", "")

    async def search_images(
        self,
        keywords: List[str],
        count: int = 4,
        orientation: str = "landscape"
    ) -> List[Dict]:
        """
        키워드로 이미지 검색

        Args:
            keywords: 검색 키워드 리스트
            count: 가져올 이미지 개수
            orientation: 이미지 방향 (landscape, portrait, squarish)

        Returns:
            이미지 정보 리스트 [{"url": "...", "caption": "...", "photographer": "..."}]
        """
        # 먼저 Unsplash 시도
        if self.unsplash_access_key:
            try:
                return await self._search_unsplash(keywords, count, orientation)
            except Exception as e:
                print(f"Unsplash 검색 실패: {e}")

        # Unsplash 실패 시 Pexels 시도
        if self.pexels_api_key:
            try:
                return await self._search_pexels(keywords, count, orientation)
            except Exception as e:
                print(f"Pexels 검색 실패: {e}")

        # API 키가 없으면 키워드 기반 플레이스홀더 이미지 반환
        print(f"⚠️ 이미지 API 키 미설정. 키워드 기반 placeholder 이미지 사용: {keywords}")
        return self._get_placeholder_images(count, keywords)

    async def _search_unsplash(
        self,
        keywords: List[str],
        count: int,
        orientation: str
    ) -> List[Dict]:
        """Unsplash API로 이미지 검색"""

        # 검색어 생성 (키워드를 조합)
        query = " ".join(keywords[:3]) if keywords else "medical health"

        url = "https://api.unsplash.com/search/photos"
        params = {
            "query": query,
            "per_page": count,
            "orientation": orientation,
            "content_filter": "high",  # 안전한 콘텐츠만
        }
        headers = {
            "Authorization": f"Client-ID {self.unsplash_access_key}"
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers, timeout=10.0)
            response.raise_for_status()
            data = response.json()

            images = []
            for result in data.get("results", [])[:count]:
                images.append({
                    "url": result["urls"]["regular"],  # 중간 크기 이미지
                    "thumb_url": result["urls"]["thumb"],  # 썸네일
                    "caption": result.get("alt_description") or result.get("description") or query,
                    "photographer": result["user"]["name"],
                    "photographer_url": result["user"]["links"]["html"],
                    "source": "unsplash"
                })

            return images

    async def _search_pexels(
        self,
        keywords: List[str],
        count: int,
        orientation: str
    ) -> List[Dict]:
        """Pexels API로 이미지 검색"""

        query = " ".join(keywords[:3]) if keywords else "medical health"

        url = "https://api.pexels.com/v1/search"
        params = {
            "query": query,
            "per_page": count,
            "orientation": orientation,
        }
        headers = {
            "Authorization": self.pexels_api_key
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers, timeout=10.0)
            response.raise_for_status()
            data = response.json()

            images = []
            for photo in data.get("photos", [])[:count]:
                images.append({
                    "url": photo["src"]["large"],  # 큰 이미지
                    "thumb_url": photo["src"]["medium"],  # 썸네일
                    "caption": f"Photo by {photo['photographer']}",
                    "photographer": photo["photographer"],
                    "photographer_url": photo["photographer_url"],
                    "source": "pexels"
                })

            return images

    def _get_placeholder_images(self, count: int, keywords: Optional[List[str]] = None) -> List[Dict]:
        """
        API 키가 없을 때 플레이스홀더 이미지 반환

        키워드에 따라 적절한 카테고리의 이미지를 제공합니다.
        (loremflickr.com 사용 - API 키 불필요, 카테고리 지원)
        """
        images = []

        # 키워드에 따른 카테고리 매핑
        category = "medical,health,clinic"
        if keywords:
            keyword_str = " ".join(keywords).lower()
            if any(k in keyword_str for k in ["치과", "dental", "이빨", "치아"]):
                category = "dental,teeth,smile"
            elif any(k in keyword_str for k in ["피부", "skin", "피부과", "derma"]):
                category = "skin,skincare,beauty"
            elif any(k in keyword_str for k in ["성형", "plastic", "수술"]):
                category = "surgery,hospital,medical"
            elif any(k in keyword_str for k in ["한의", "한방", "침"]):
                category = "acupuncture,herb,traditional"
            elif any(k in keyword_str for k in ["정형", "척추", "관절"]):
                category = "spine,orthopedic,bone"
            elif any(k in keyword_str for k in ["안과", "눈", "eye"]):
                category = "eye,vision,ophthalmology"

        for i in range(count):
            # loremflickr.com - 키워드 기반 무료 이미지
            # 각 이미지마다 다른 lock 값을 사용하여 다양한 이미지 확보
            lock_value = 1000 + i
            images.append({
                "url": f"https://loremflickr.com/800/600/{category}?lock={lock_value}",
                "thumb_url": f"https://loremflickr.com/200/150/{category}?lock={lock_value}",
                "caption": f"의료 관련 이미지 {i + 1}",
                "photographer": "LoremFlickr",
                "photographer_url": "https://loremflickr.com",
                "source": "placeholder",
                "notice": "API 키를 설정하면 더 정확한 이미지를 검색할 수 있습니다."
            })

        return images

    async def download_image(self, url: str) -> bytes:
        """
        이미지 URL에서 바이너리 데이터 다운로드

        Args:
            url: 이미지 URL

        Returns:
            이미지 바이너리 데이터
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            return response.content


# 싱글톤 인스턴스
image_search_service = ImageSearchService()
