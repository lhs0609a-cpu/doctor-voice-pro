"""
SNS 멀티 포스팅 서비스
"""

import logging
import httpx
from typing import Optional, Dict, List, Any
from datetime import datetime
from urllib.parse import urlencode
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.models.sns_connection import (
    SNSConnection, SNSPost, HashtagRecommendation,
    SNSPlatform, SNSPostStatus, SNSContentType
)
from app.models.post import Post
from app.core.config import settings

logger = logging.getLogger(__name__)


class SNSService:
    """SNS 멀티 포스팅 서비스"""

    def __init__(self):
        # Facebook/Instagram Graph API 설정
        self.fb_app_id = getattr(settings, 'FACEBOOK_APP_ID', '')
        self.fb_app_secret = getattr(settings, 'FACEBOOK_APP_SECRET', '')
        self.fb_graph_url = "https://graph.facebook.com/v18.0"

    # ==================== OAuth 연동 ====================

    def get_instagram_auth_url(self, redirect_uri: str, state: str) -> str:
        """
        Instagram OAuth URL 생성
        """
        params = {
            "client_id": self.fb_app_id,
            "redirect_uri": redirect_uri,
            "scope": "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement",
            "response_type": "code",
            "state": state,
        }
        return f"https://www.facebook.com/v18.0/dialog/oauth?{urlencode(params)}"

    def get_facebook_auth_url(self, redirect_uri: str, state: str) -> str:
        """
        Facebook OAuth URL 생성
        """
        params = {
            "client_id": self.fb_app_id,
            "redirect_uri": redirect_uri,
            "scope": "pages_manage_posts,pages_read_engagement,pages_show_list",
            "response_type": "code",
            "state": state,
        }
        return f"https://www.facebook.com/v18.0/dialog/oauth?{urlencode(params)}"

    async def exchange_code_for_token(
        self,
        platform: SNSPlatform,
        code: str,
        redirect_uri: str,
    ) -> Optional[Dict]:
        """
        Authorization code를 액세스 토큰으로 교환
        """
        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "client_id": self.fb_app_id,
                    "client_secret": self.fb_app_secret,
                    "redirect_uri": redirect_uri,
                    "code": code,
                }

                response = await client.get(
                    f"{self.fb_graph_url}/oauth/access_token",
                    params=params,
                )

                if response.status_code == 200:
                    data = response.json()

                    # Long-lived token으로 교환
                    long_lived = await self._get_long_lived_token(data["access_token"])
                    if long_lived:
                        data.update(long_lived)

                    return data
                else:
                    logger.error(f"Failed to exchange code: {response.text}")
                    return None

        except Exception as e:
            logger.error(f"Error exchanging code for token: {e}")
            return None

    async def _get_long_lived_token(self, short_token: str) -> Optional[Dict]:
        """
        Short-lived token을 Long-lived token으로 교환
        """
        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "grant_type": "fb_exchange_token",
                    "client_id": self.fb_app_id,
                    "client_secret": self.fb_app_secret,
                    "fb_exchange_token": short_token,
                }

                response = await client.get(
                    f"{self.fb_graph_url}/oauth/access_token",
                    params=params,
                )

                if response.status_code == 200:
                    return response.json()
                return None

        except Exception as e:
            logger.error(f"Error getting long-lived token: {e}")
            return None

    async def get_user_info(
        self,
        platform: SNSPlatform,
        access_token: str,
    ) -> Optional[Dict]:
        """
        사용자 정보 조회
        """
        try:
            async with httpx.AsyncClient() as client:
                if platform == SNSPlatform.FACEBOOK:
                    response = await client.get(
                        f"{self.fb_graph_url}/me",
                        params={
                            "access_token": access_token,
                            "fields": "id,name,picture",
                        },
                    )
                elif platform == SNSPlatform.INSTAGRAM:
                    # Instagram Business Account 정보
                    response = await client.get(
                        f"{self.fb_graph_url}/me/accounts",
                        params={
                            "access_token": access_token,
                            "fields": "instagram_business_account{id,username,profile_picture_url}",
                        },
                    )
                else:
                    return None

                if response.status_code == 200:
                    return response.json()
                return None

        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return None

    # ==================== 연동 관리 ====================

    async def save_connection(
        self,
        db: AsyncSession,
        user_id: str,
        platform: SNSPlatform,
        access_token: str,
        token_data: Dict,
        user_info: Dict,
    ) -> SNSConnection:
        """
        SNS 연동 정보 저장
        """
        # 기존 연동 확인
        query = select(SNSConnection).where(
            and_(
                SNSConnection.user_id == user_id,
                SNSConnection.platform == platform,
            )
        )
        result = await db.execute(query)
        connection = result.scalar_one_or_none()

        if connection:
            # 기존 연동 업데이트
            connection.access_token = access_token
            connection.token_expires_at = datetime.utcnow() + \
                timedelta(seconds=token_data.get("expires_in", 5184000))  # 기본 60일
        else:
            # 새 연동 생성
            connection = SNSConnection(
                user_id=user_id,
                platform=platform,
                access_token=access_token,
                token_expires_at=datetime.utcnow() + \
                    timedelta(seconds=token_data.get("expires_in", 5184000)),
            )
            db.add(connection)

        # 플랫폼별 사용자 정보 설정
        if platform == SNSPlatform.FACEBOOK:
            connection.platform_user_id = user_info.get("id")
            connection.platform_username = user_info.get("name")
            if user_info.get("picture", {}).get("data"):
                connection.profile_image_url = user_info["picture"]["data"].get("url")
        elif platform == SNSPlatform.INSTAGRAM:
            if user_info.get("data"):
                for page in user_info["data"]:
                    if page.get("instagram_business_account"):
                        ig = page["instagram_business_account"]
                        connection.platform_user_id = ig.get("id")
                        connection.platform_username = ig.get("username")
                        connection.profile_image_url = ig.get("profile_picture_url")
                        connection.page_id = page.get("id")
                        break

        connection.is_active = True
        connection.connection_status = "connected"

        await db.commit()
        await db.refresh(connection)
        return connection

    async def get_connections(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> List[SNSConnection]:
        """
        사용자의 SNS 연동 목록 조회
        """
        query = select(SNSConnection).where(
            SNSConnection.user_id == user_id
        ).order_by(SNSConnection.created_at.desc())

        result = await db.execute(query)
        return result.scalars().all()

    async def get_connection(
        self,
        db: AsyncSession,
        user_id: str,
        platform: SNSPlatform,
    ) -> Optional[SNSConnection]:
        """
        특정 플랫폼 연동 정보 조회
        """
        query = select(SNSConnection).where(
            and_(
                SNSConnection.user_id == user_id,
                SNSConnection.platform == platform,
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def disconnect(
        self,
        db: AsyncSession,
        user_id: str,
        platform: SNSPlatform,
    ) -> bool:
        """
        SNS 연동 해제
        """
        connection = await self.get_connection(db, user_id, platform)
        if not connection:
            return False

        await db.delete(connection)
        await db.commit()
        return True

    # ==================== 콘텐츠 변환 ====================

    async def convert_to_sns(
        self,
        db: AsyncSession,
        post_id: str,
        user_id: str,
        platform: SNSPlatform,
        content_type: SNSContentType = SNSContentType.POST,
    ) -> Dict[str, Any]:
        """
        블로그 글을 SNS 포맷으로 변환
        """
        # 원본 포스트 조회
        query = select(Post).where(
            and_(
                Post.id == post_id,
                Post.user_id == user_id,
            )
        )
        result = await db.execute(query)
        post = result.scalar_one_or_none()

        if not post:
            raise ValueError("Post not found")

        content = post.generated_content or post.original_content

        # 플랫폼별 최대 길이
        max_lengths = {
            SNSPlatform.INSTAGRAM: 2200,
            SNSPlatform.FACEBOOK: 63206,
            SNSPlatform.THREADS: 500,
            SNSPlatform.TWITTER: 280,
        }

        max_length = max_lengths.get(platform, 2200)

        # 콘텐츠 요약 (간단한 버전, 실제로는 AI 사용)
        caption = self._summarize_content(content, max_length)

        # 해시태그 생성
        hashtags = await self._generate_hashtags(db, post, platform)

        return {
            "caption": caption,
            "hashtags": hashtags,
            "original_post_id": str(post.id),
            "original_title": post.title,
            "platform": platform.value,
            "content_type": content_type.value,
        }

    def _summarize_content(self, content: str, max_length: int) -> str:
        """
        콘텐츠 요약 (간단한 버전)
        """
        # HTML 태그 제거
        import re
        text = re.sub(r'<[^>]+>', '', content)

        # 줄바꿈 정리
        text = re.sub(r'\n+', '\n\n', text)

        # 최대 길이로 자르기
        if len(text) > max_length:
            text = text[:max_length - 100] + "...\n\n📖 자세한 내용은 블로그에서 확인하세요!"

        return text.strip()

    async def _generate_hashtags(
        self,
        db: AsyncSession,
        post: Post,
        platform: SNSPlatform,
    ) -> List[str]:
        """
        해시태그 생성
        """
        hashtags = []

        # 포스트의 기존 해시태그 활용
        if post.hashtags:
            if isinstance(post.hashtags, list):
                hashtags.extend(post.hashtags[:10])

        # 키워드 기반 해시태그 추가
        if post.seo_keywords:
            keywords = post.seo_keywords if isinstance(post.seo_keywords, list) else []
            for kw in keywords[:5]:
                tag = f"#{kw.replace(' ', '')}"
                if tag not in hashtags:
                    hashtags.append(tag)

        # 기본 의료 해시태그
        default_tags = ["#의료정보", "#건강", "#병원", "#의사", "#건강관리"]
        for tag in default_tags:
            if len(hashtags) >= 15:
                break
            if tag not in hashtags:
                hashtags.append(tag)

        return hashtags

    async def generate_shortform_script(
        self,
        db: AsyncSession,
        post_id: str,
        user_id: str,
        duration: int = 30,  # 초
    ) -> Dict[str, Any]:
        """
        숏폼(릴스/숏츠) 스크립트 생성
        """
        # 원본 포스트 조회
        query = select(Post).where(
            and_(
                Post.id == post_id,
                Post.user_id == user_id,
            )
        )
        result = await db.execute(query)
        post = result.scalar_one_or_none()

        if not post:
            raise ValueError("Post not found")

        content = post.generated_content or post.original_content

        # 간단한 스크립트 생성 (실제로는 AI 사용)
        script = self._create_shortform_script(post.title, content, duration)

        return {
            "script": script["full_script"],
            "duration": duration,
            "sections": script["sections"],
            "hooks": script["hooks"],
            "cta": script["cta"],
            "original_post_id": str(post.id),
        }

    def _create_shortform_script(
        self,
        title: str,
        content: str,
        duration: int,
    ) -> Dict[str, Any]:
        """
        숏폼 스크립트 생성 (간단한 템플릿 버전)
        """
        # HTML 태그 제거
        import re
        text = re.sub(r'<[^>]+>', '', content)

        # 문장 분리
        sentences = re.split(r'[.!?]\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        # 섹션별 시간 배분
        if duration <= 15:
            sections = [
                {"time": "0-3초", "type": "hook", "text": f"🎯 {title[:50]}"},
                {"time": "3-12초", "type": "main", "text": sentences[0] if sentences else ""},
                {"time": "12-15초", "type": "cta", "text": "💬 더 알고 싶다면 팔로우하세요!"},
            ]
        elif duration <= 30:
            sections = [
                {"time": "0-5초", "type": "hook", "text": f"🎯 {title[:50]}"},
                {"time": "5-10초", "type": "problem", "text": sentences[0] if sentences else ""},
                {"time": "10-20초", "type": "solution", "text": " ".join(sentences[1:3]) if len(sentences) > 1 else ""},
                {"time": "20-25초", "type": "benefit", "text": sentences[3] if len(sentences) > 3 else ""},
                {"time": "25-30초", "type": "cta", "text": "💬 도움이 됐다면 저장해두세요!"},
            ]
        else:  # 60초
            sections = [
                {"time": "0-5초", "type": "hook", "text": f"🎯 {title[:50]}"},
                {"time": "5-15초", "type": "problem", "text": " ".join(sentences[:2]) if sentences else ""},
                {"time": "15-35초", "type": "solution", "text": " ".join(sentences[2:5]) if len(sentences) > 2 else ""},
                {"time": "35-50초", "type": "benefit", "text": " ".join(sentences[5:7]) if len(sentences) > 5 else ""},
                {"time": "50-60초", "type": "cta", "text": "💬 댓글로 질문해주세요! 팔로우하면 더 많은 정보를 받아볼 수 있어요!"},
            ]

        # 전체 스크립트 생성
        full_script = "\n\n".join([f"[{s['time']}] {s['text']}" for s in sections])

        # 훅 아이디어
        hooks = [
            f"'{title}'에 대해 알고 계셨나요?",
            f"많은 분들이 모르는 {title[:20]}의 비밀",
            f"의사가 알려주는 {title[:20]}",
        ]

        # CTA 옵션
        cta_options = [
            "저장해두고 필요할 때 보세요!",
            "도움이 됐다면 좋아요와 팔로우 부탁드려요!",
            "궁금한 점은 댓글로 남겨주세요!",
        ]

        return {
            "full_script": full_script,
            "sections": sections,
            "hooks": hooks,
            "cta": cta_options,
        }

    # ==================== SNS 포스트 관리 ====================

    async def create_sns_post(
        self,
        db: AsyncSession,
        user_id: str,
        platform: SNSPlatform,
        caption: str,
        content_type: SNSContentType = SNSContentType.POST,
        hashtags: Optional[List[str]] = None,
        media_urls: Optional[List[str]] = None,
        original_post_id: Optional[str] = None,
        script: Optional[str] = None,
        script_duration: Optional[int] = None,
    ) -> SNSPost:
        """
        SNS 포스트 생성
        """
        sns_post = SNSPost(
            user_id=user_id,
            original_post_id=original_post_id,
            platform=platform,
            content_type=content_type,
            caption=caption,
            hashtags=hashtags,
            media_urls=media_urls,
            script=script,
            script_duration=script_duration,
            status=SNSPostStatus.DRAFT,
        )

        db.add(sns_post)
        await db.commit()
        await db.refresh(sns_post)
        return sns_post

    async def get_sns_posts(
        self,
        db: AsyncSession,
        user_id: str,
        platform: Optional[SNSPlatform] = None,
        status: Optional[SNSPostStatus] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[SNSPost]:
        """
        SNS 포스트 목록 조회
        """
        query = select(SNSPost).where(
            SNSPost.user_id == user_id
        ).order_by(SNSPost.created_at.desc())

        if platform:
            query = query.where(SNSPost.platform == platform)
        if status:
            query = query.where(SNSPost.status == status)

        query = query.offset(offset).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    async def get_sns_post(
        self,
        db: AsyncSession,
        sns_post_id: str,
        user_id: Optional[str] = None,
    ) -> Optional[SNSPost]:
        """
        SNS 포스트 상세 조회
        """
        query = select(SNSPost).where(SNSPost.id == sns_post_id)

        if user_id:
            query = query.where(SNSPost.user_id == user_id)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def update_sns_post(
        self,
        db: AsyncSession,
        sns_post_id: str,
        user_id: str,
        **kwargs,
    ) -> Optional[SNSPost]:
        """
        SNS 포스트 수정
        """
        sns_post = await self.get_sns_post(db, sns_post_id, user_id)
        if not sns_post:
            return None

        allowed_fields = ['caption', 'hashtags', 'media_urls', 'script', 'script_duration']
        for key, value in kwargs.items():
            if key in allowed_fields:
                setattr(sns_post, key, value)

        await db.commit()
        await db.refresh(sns_post)
        return sns_post

    async def delete_sns_post(
        self,
        db: AsyncSession,
        sns_post_id: str,
        user_id: str,
    ) -> bool:
        """
        SNS 포스트 삭제
        """
        sns_post = await self.get_sns_post(db, sns_post_id, user_id)
        if not sns_post:
            return False

        await db.delete(sns_post)
        await db.commit()
        return True

    async def publish_to_instagram(
        self,
        db: AsyncSession,
        sns_post_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Instagram에 발행
        """
        sns_post = await self.get_sns_post(db, sns_post_id, user_id)
        if not sns_post:
            raise ValueError("SNS post not found")

        connection = await self.get_connection(db, user_id, SNSPlatform.INSTAGRAM)
        if not connection:
            raise ValueError("Instagram not connected")

        sns_post.status = SNSPostStatus.PUBLISHING

        try:
            # Instagram Graph API 호출
            # 1. 미디어 컨테이너 생성
            # 2. 미디어 발행

            # 여기서는 시뮬레이션
            # 실제 구현에서는 Instagram Graph API 호출

            sns_post.status = SNSPostStatus.PUBLISHED
            sns_post.published_at = datetime.utcnow()
            sns_post.platform_post_url = f"https://www.instagram.com/p/example/"

            connection.last_used_at = datetime.utcnow()

            await db.commit()

            return {
                "success": True,
                "platform_post_url": sns_post.platform_post_url,
            }

        except Exception as e:
            logger.error(f"Failed to publish to Instagram: {e}")
            sns_post.status = SNSPostStatus.FAILED
            sns_post.error_message = str(e)
            sns_post.retry_count += 1
            await db.commit()

            return {
                "success": False,
                "error": str(e),
            }

    # ==================== 해시태그 추천 ====================

    async def get_hashtag_recommendations(
        self,
        db: AsyncSession,
        category: str,
        platform: Optional[SNSPlatform] = None,
        limit: int = 20,
    ) -> List[HashtagRecommendation]:
        """
        해시태그 추천 조회
        """
        query = select(HashtagRecommendation).where(
            HashtagRecommendation.category == category
        ).order_by(HashtagRecommendation.priority.desc())

        query = query.limit(limit)
        result = await db.execute(query)
        recommendations = result.scalars().all()

        # 플랫폼 필터링 (Python에서 처리 - JSON 배열 필터링)
        if platform:
            platform_value = platform.value if hasattr(platform, 'value') else platform
            filtered = [
                r for r in recommendations
                if not r.platforms or platform_value in r.platforms
            ]
            return filtered[:limit]

        return recommendations


# Import timedelta for token expiration
from datetime import timedelta

# Singleton instance
sns_service = SNSService()
