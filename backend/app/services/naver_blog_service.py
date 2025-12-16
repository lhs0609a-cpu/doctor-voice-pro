"""
네이버 블로그 API 연동 서비스
OAuth 2.0 인증 및 블로그 포스팅 자동화
"""

import httpx
import logging
from typing import Optional, Dict, List
from urllib.parse import urlencode

from app.core.config import settings

logger = logging.getLogger(__name__)


class NaverBlogService:
    """네이버 블로그 API 서비스"""

    def __init__(self):
        self.client_id = settings.NAVER_CLIENT_ID
        self.client_secret = settings.NAVER_CLIENT_SECRET
        self.base_url = "https://openapi.naver.com"
        self.auth_url = "https://nid.naver.com/oauth2.0"

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        """
        OAuth 인증 URL 생성

        Args:
            redirect_uri: 콜백 URL
            state: CSRF 방지를 위한 state 값

        Returns:
            네이버 로그인 페이지 URL
        """
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "state": state,
        }
        return f"{self.auth_url}/authorize?{urlencode(params)}"

    async def get_access_token(
        self, code: str, state: str, redirect_uri: str
    ) -> Optional[Dict]:
        """
        Authorization code를 사용하여 액세스 토큰 발급

        Args:
            code: 인증 코드
            state: state 값
            redirect_uri: 콜백 URL

        Returns:
            {
                "access_token": "...",
                "refresh_token": "...",
                "token_type": "bearer",
                "expires_in": 3600
            }
        """
        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "grant_type": "authorization_code",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "state": state,
                    "redirect_uri": redirect_uri,
                }

                response = await client.post(
                    f"{self.auth_url}/token",
                    data=params,
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(
                        f"Failed to get access token: {response.status_code} - {response.text}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Error getting access token: {e}")
            return None

    async def refresh_access_token(self, refresh_token: str) -> Optional[Dict]:
        """
        리프레시 토큰으로 새 액세스 토큰 발급

        Args:
            refresh_token: 리프레시 토큰

        Returns:
            새로운 토큰 정보
        """
        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "grant_type": "refresh_token",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                }

                response = await client.post(
                    f"{self.auth_url}/token",
                    data=params,
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(
                        f"Failed to refresh token: {response.status_code} - {response.text}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return None

    async def get_user_profile(self, access_token: str) -> Optional[Dict]:
        """
        네이버 사용자 프로필 조회

        Args:
            access_token: 액세스 토큰

        Returns:
            사용자 프로필 정보
        """
        try:
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {access_token}"}

                response = await client.get(
                    f"{self.base_url}/v1/nid/me",
                    headers=headers,
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(
                        f"Failed to get user profile: {response.status_code} - {response.text}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return None

    async def get_blog_info(self, access_token: str) -> Optional[Dict]:
        """
        블로그 정보 조회

        Args:
            access_token: 액세스 토큰

        Returns:
            블로그 정보
        """
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "X-Naver-Client-Id": self.client_id,
                    "X-Naver-Client-Secret": self.client_secret,
                }

                response = await client.get(
                    f"{self.base_url}/blog/getBlogInfo.json",
                    headers=headers,
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(
                        f"Failed to get blog info: {response.status_code} - {response.text}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Error getting blog info: {e}")
            return None

    async def get_categories(self, access_token: str, blog_id: str) -> List[Dict]:
        """
        블로그 카테고리 목록 조회

        Args:
            access_token: 액세스 토큰
            blog_id: 블로그 ID

        Returns:
            카테고리 목록
        """
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "X-Naver-Client-Id": self.client_id,
                    "X-Naver-Client-Secret": self.client_secret,
                }

                response = await client.get(
                    f"{self.base_url}/blog/listCategory.json",
                    headers=headers,
                    params={"blogId": blog_id},
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get("categories", [])
                else:
                    logger.error(
                        f"Failed to get categories: {response.status_code} - {response.text}"
                    )
                    return []

        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            return []

    async def create_post(
        self,
        access_token: str,
        title: str,
        content: str,
        category_no: Optional[int] = None,
        open_type: str = "0",  # 0: 전체공개, 1: 이웃공개, 2: 비공개
        tag: Optional[List[str]] = None,
    ) -> Optional[Dict]:
        """
        블로그 포스트 작성

        Args:
            access_token: 액세스 토큰
            title: 포스트 제목
            content: 포스트 내용 (HTML)
            category_no: 카테고리 번호
            open_type: 공개 설정
            tag: 태그 목록

        Returns:
            작성된 포스트 정보
        """
        try:
            # Convert content to HTML if it's plain text
            html_content = self._convert_to_html(content)

            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "X-Naver-Client-Id": self.client_id,
                    "X-Naver-Client-Secret": self.client_secret,
                    "Content-Type": "application/json",
                }

                data = {
                    "title": title,
                    "contents": html_content,
                    "openType": open_type,
                }

                if category_no:
                    data["categoryNo"] = category_no

                if tag:
                    data["tag"] = ",".join(tag)

                response = await client.post(
                    f"{self.base_url}/blog/writePost.json",
                    headers=headers,
                    json=data,
                )

                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Successfully created blog post: {result}")
                    return result
                else:
                    logger.error(
                        f"Failed to create post: {response.status_code} - {response.text}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Error creating post: {e}")
            return None

    async def update_post(
        self,
        access_token: str,
        post_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        category_no: Optional[int] = None,
        open_type: Optional[str] = None,
        tag: Optional[List[str]] = None,
    ) -> Optional[Dict]:
        """
        블로그 포스트 수정

        Args:
            access_token: 액세스 토큰
            post_id: 포스트 ID
            title: 포스트 제목
            content: 포스트 내용
            category_no: 카테고리 번호
            open_type: 공개 설정
            tag: 태그 목록

        Returns:
            수정된 포스트 정보
        """
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "X-Naver-Client-Id": self.client_id,
                    "X-Naver-Client-Secret": self.client_secret,
                    "Content-Type": "application/json",
                }

                data = {"logNo": post_id}

                if title:
                    data["title"] = title
                if content:
                    data["contents"] = self._convert_to_html(content)
                if category_no:
                    data["categoryNo"] = category_no
                if open_type:
                    data["openType"] = open_type
                if tag:
                    data["tag"] = ",".join(tag)

                response = await client.post(
                    f"{self.base_url}/blog/modifyPost.json",
                    headers=headers,
                    json=data,
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(
                        f"Failed to update post: {response.status_code} - {response.text}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Error updating post: {e}")
            return None

    async def delete_post(self, access_token: str, post_id: str) -> bool:
        """
        블로그 포스트 삭제

        Args:
            access_token: 액세스 토큰
            post_id: 포스트 ID

        Returns:
            삭제 성공 여부
        """
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "X-Naver-Client-Id": self.client_id,
                    "X-Naver-Client-Secret": self.client_secret,
                }

                response = await client.post(
                    f"{self.base_url}/blog/deletePost.json",
                    headers=headers,
                    params={"logNo": post_id},
                )

                if response.status_code == 200:
                    return True
                else:
                    logger.error(
                        f"Failed to delete post: {response.status_code} - {response.text}"
                    )
                    return False

        except Exception as e:
            logger.error(f"Error deleting post: {e}")
            return False

    def _convert_to_html(self, content: str) -> str:
        """
        플레인 텍스트를 HTML로 변환

        Args:
            content: 플레인 텍스트

        Returns:
            HTML 형식 문자열
        """
        # Simple conversion: replace newlines with <br> tags
        lines = content.split("\n")
        html_lines = []

        for line in lines:
            if line.strip():
                # Check if line starts with a header marker
                if line.startswith("# "):
                    html_lines.append(f"<h1>{line[2:]}</h1>")
                elif line.startswith("## "):
                    html_lines.append(f"<h2>{line[3:]}</h2>")
                elif line.startswith("### "):
                    html_lines.append(f"<h3>{line[4:]}</h3>")
                else:
                    html_lines.append(f"<p>{line}</p>")
            else:
                html_lines.append("<br>")

        return "\n".join(html_lines)


# Global instance
naver_blog_service = NaverBlogService()
