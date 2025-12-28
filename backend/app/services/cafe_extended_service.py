"""
카페 확장 서비스
- 대댓글 자동화
- 게시판 타겟팅
- 인기글 분석
- 팔로우/좋아요 활동
"""

import uuid
import random
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.cafe_extended import (
    CafeBoard, CommentReply, ReplyTemplate,
    CafePostImage, ImageLibrary, PopularPost,
    PopularPostPattern, EngagementActivity, EngagementSchedule,
    ContentPerformance, ReplyStatus, EngagementType, PopularPostCategory
)
from app.models.cafe import CafeCommunity, CafeContent


class BoardTargetingService:
    """게시판 타겟팅 서비스"""

    async def add_board(
        self,
        db: AsyncSession,
        user_id: str,
        cafe_id: str,
        board_id: str,
        board_name: str,
        board_url: Optional[str] = None,
        priority: int = 1,
        allow_comment: bool = True,
        allow_post: bool = False,
        allow_reply: bool = True,
        daily_comment_limit: int = 10,
        daily_post_limit: int = 2
    ) -> CafeBoard:
        """게시판 추가"""
        board = CafeBoard(
            id=str(uuid.uuid4()),
            user_id=user_id,
            cafe_id=cafe_id,
            board_id=board_id,
            board_name=board_name,
            board_url=board_url,
            priority=priority,
            allow_comment=allow_comment,
            allow_post=allow_post,
            allow_reply=allow_reply,
            daily_comment_limit=daily_comment_limit,
            daily_post_limit=daily_post_limit
        )
        db.add(board)
        await db.commit()
        await db.refresh(board)
        return board

    async def get_boards(
        self,
        db: AsyncSession,
        user_id: str,
        cafe_id: Optional[str] = None,
        is_target: bool = True
    ) -> List[CafeBoard]:
        """게시판 목록 조회"""
        query = select(CafeBoard).where(
            and_(
                CafeBoard.user_id == user_id,
                CafeBoard.is_target == is_target
            )
        )

        if cafe_id:
            query = query.where(CafeBoard.cafe_id == cafe_id)

        query = query.order_by(CafeBoard.priority.desc())

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_target_board(
        self,
        db: AsyncSession,
        user_id: str,
        cafe_id: str,
        for_comment: bool = True
    ) -> Optional[CafeBoard]:
        """타겟 게시판 선택 (우선순위 기반)"""
        query = select(CafeBoard).where(
            and_(
                CafeBoard.user_id == user_id,
                CafeBoard.cafe_id == cafe_id,
                CafeBoard.is_target == True
            )
        )

        if for_comment:
            query = query.where(CafeBoard.allow_comment == True)
        else:
            query = query.where(CafeBoard.allow_post == True)

        query = query.order_by(CafeBoard.priority.desc())

        result = await db.execute(query)
        boards = list(result.scalars().all())

        if not boards:
            return None

        # 우선순위 가중 랜덤 선택
        weights = [b.priority for b in boards]
        selected = random.choices(boards, weights=weights, k=1)[0]

        return selected

    async def update_board_stats(
        self,
        db: AsyncSession,
        board_id: str,
        comment_posted: bool = False,
        post_created: bool = False,
        like_received: bool = False
    ):
        """게시판 통계 업데이트"""
        result = await db.execute(
            select(CafeBoard).where(CafeBoard.id == board_id)
        )
        board = result.scalar_one_or_none()

        if board:
            if comment_posted:
                board.total_comments += 1
            if post_created:
                board.total_posts += 1
            if like_received:
                board.total_likes += 1

            await db.commit()

    async def set_board_keywords(
        self,
        db: AsyncSession,
        board_id: str,
        include_keywords: Optional[List[str]] = None,
        exclude_keywords: Optional[List[str]] = None
    ):
        """게시판 키워드 필터 설정"""
        result = await db.execute(
            select(CafeBoard).where(CafeBoard.id == board_id)
        )
        board = result.scalar_one_or_none()

        if board:
            if include_keywords is not None:
                board.include_keywords = include_keywords
            if exclude_keywords is not None:
                board.exclude_keywords = exclude_keywords

            await db.commit()


class ReplyAutomationService:
    """대댓글 자동화 서비스"""

    async def track_reply(
        self,
        db: AsyncSession,
        user_id: str,
        content_id: str,
        original_comment_id: str,
        original_post_url: str,
        reply_id: str,
        reply_author: str,
        reply_author_id: str,
        reply_content: str,
        reply_at: datetime
    ) -> CommentReply:
        """대댓글 추적"""
        reply = CommentReply(
            id=str(uuid.uuid4()),
            user_id=user_id,
            original_content_id=content_id,
            original_comment_id=original_comment_id,
            original_post_url=original_post_url,
            reply_id=reply_id,
            reply_author=reply_author,
            reply_author_id=reply_author_id,
            reply_content=reply_content,
            reply_at=reply_at,
            sentiment=self._analyze_sentiment(reply_content),
            requires_response=self._check_requires_response(reply_content),
            urgency=self._calculate_urgency(reply_content)
        )
        db.add(reply)
        await db.commit()
        await db.refresh(reply)
        return reply

    def _analyze_sentiment(self, content: str) -> str:
        """감정 분석"""
        positive_words = ["감사", "좋아", "도움", "추천", "최고", "짱"]
        negative_words = ["싫어", "별로", "광고", "스팸", "신고"]

        pos_count = sum(1 for w in positive_words if w in content)
        neg_count = sum(1 for w in negative_words if w in content)

        if pos_count > neg_count:
            return "positive"
        elif neg_count > pos_count:
            return "negative"
        return "neutral"

    def _check_requires_response(self, content: str) -> bool:
        """응답 필요 여부"""
        question_indicators = ["?", "어디", "뭐", "어떻게", "왜", "언제"]
        return any(q in content for q in question_indicators)

    def _calculate_urgency(self, content: str) -> str:
        """긴급도 계산"""
        urgent_words = ["급해", "빨리", "지금", "오늘", "당장"]
        if any(w in content for w in urgent_words):
            return "high"
        if self._check_requires_response(content):
            return "medium"
        return "low"

    async def get_pending_replies(
        self,
        db: AsyncSession,
        user_id: str,
        limit: int = 20
    ) -> List[CommentReply]:
        """응답 대기 대댓글 조회"""
        result = await db.execute(
            select(CommentReply).where(
                and_(
                    CommentReply.user_id == user_id,
                    CommentReply.status == ReplyStatus.PENDING.value,
                    CommentReply.requires_response == True
                )
            ).order_by(
                # 긴급도 우선
                CommentReply.urgency.desc(),
                CommentReply.reply_at.asc()
            ).limit(limit)
        )
        return list(result.scalars().all())

    async def create_reply_template(
        self,
        db: AsyncSession,
        user_id: str,
        name: str,
        category: str,
        template_content: str,
        trigger_keywords: Optional[List[str]] = None,
        trigger_sentiment: Optional[str] = None,
        tone: str = "friendly",
        include_promotion: bool = False
    ) -> ReplyTemplate:
        """대댓글 템플릿 생성"""
        template = ReplyTemplate(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            category=category,
            template_content=template_content,
            trigger_keywords=trigger_keywords,
            trigger_sentiment=trigger_sentiment,
            tone=tone,
            include_promotion=include_promotion
        )
        db.add(template)
        await db.commit()
        await db.refresh(template)
        return template

    async def find_matching_template(
        self,
        db: AsyncSession,
        user_id: str,
        reply_content: str,
        sentiment: str
    ) -> Optional[ReplyTemplate]:
        """매칭 템플릿 찾기"""
        result = await db.execute(
            select(ReplyTemplate).where(
                and_(
                    ReplyTemplate.user_id == user_id,
                    ReplyTemplate.is_active == True
                )
            )
        )
        templates = list(result.scalars().all())

        for template in templates:
            # 감정 매칭
            if template.trigger_sentiment and template.trigger_sentiment != sentiment:
                continue

            # 키워드 매칭
            if template.trigger_keywords:
                if any(k in reply_content for k in template.trigger_keywords):
                    return template

        return None

    async def mark_reply_sent(
        self,
        db: AsyncSession,
        reply_id: str,
        auto_reply_content: str,
        reply_url: str
    ):
        """응답 완료 표시"""
        result = await db.execute(
            select(CommentReply).where(CommentReply.id == reply_id)
        )
        reply = result.scalar_one_or_none()

        if reply:
            reply.status = ReplyStatus.REPLIED.value
            reply.is_replied = True
            reply.replied_at = datetime.utcnow()
            reply.auto_reply_content = auto_reply_content
            reply.reply_url = reply_url

            await db.commit()


class PopularPostAnalysisService:
    """인기글 분석 서비스"""

    async def save_popular_post(
        self,
        db: AsyncSession,
        user_id: str,
        cafe_id: str,
        post_data: Dict[str, Any],
        category: str = PopularPostCategory.HOT.value
    ) -> PopularPost:
        """인기글 저장"""
        post = PopularPost(
            id=str(uuid.uuid4()),
            user_id=user_id,
            cafe_id=cafe_id,
            post_id=post_data.get("post_id"),
            article_id=post_data.get("article_id"),
            board_id=post_data.get("board_id"),
            title=post_data.get("title"),
            content=post_data.get("content"),
            url=post_data.get("url"),
            author_name=post_data.get("author_name"),
            author_id=post_data.get("author_id"),
            category=category,
            view_count=post_data.get("view_count", 0),
            comment_count=post_data.get("comment_count", 0),
            like_count=post_data.get("like_count", 0),
            posted_at=post_data.get("posted_at")
        )

        # AI 분석
        content = post_data.get("content", "")
        post.topic = self._extract_topic(post_data.get("title", ""))
        post.keywords = self._extract_keywords(content)
        post.structure = self._analyze_structure(content)
        post.tone = self._detect_tone(content)
        post.content_length = len(content)
        post.image_count = post_data.get("image_count", 0)
        post.success_factors = self._analyze_success_factors(post_data)
        post.reference_score = self._calculate_reference_score(post)

        db.add(post)
        await db.commit()
        await db.refresh(post)
        return post

    def _extract_topic(self, title: str) -> str:
        """주제 추출"""
        topic_patterns = {
            "후기": ["후기", "리뷰", "사용기", "체험"],
            "질문": ["질문", "?", "어떻게", "뭐가"],
            "정보": ["정보", "팁", "방법", "노하우"],
            "추천": ["추천", "좋은", "베스트"],
            "공유": ["공유", "나눔", "알려드"]
        }

        for topic, keywords in topic_patterns.items():
            if any(k in title for k in keywords):
                return topic

        return "일반"

    def _extract_keywords(self, content: str) -> List[str]:
        """키워드 추출"""
        import re
        # 간단한 명사 추출 (정규식 기반)
        words = re.findall(r'[가-힣]{2,}', content)

        # 빈도 계산
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1

        # 상위 10개
        sorted_words = sorted(
            word_freq.items(), key=lambda x: x[1], reverse=True
        )
        return [w[0] for w in sorted_words[:10]]

    def _analyze_structure(self, content: str) -> Dict[str, Any]:
        """구조 분석"""
        paragraphs = content.split("\n\n")
        lines = content.split("\n")

        has_list = any(
            line.strip().startswith(("-", "•", "1.", "2."))
            for line in lines
        )

        return {
            "paragraph_count": len([p for p in paragraphs if p.strip()]),
            "line_count": len([l for l in lines if l.strip()]),
            "has_list": has_list,
            "has_images": "[이미지]" in content or "사진" in content,
            "avg_paragraph_length": len(content) / max(len(paragraphs), 1)
        }

    def _detect_tone(self, content: str) -> str:
        """어조 감지"""
        # 간단한 휴리스틱
        if "ㅋㅋ" in content or "ㅎㅎ" in content:
            return "casual"
        if "합니다" in content or "드립니다" in content:
            return "formal"
        return "neutral"

    def _analyze_success_factors(self, post_data: Dict[str, Any]) -> List[str]:
        """성공 요인 분석"""
        factors = []

        title = post_data.get("title", "")
        content = post_data.get("content", "")

        # 제목 분석
        if len(title) >= 10 and len(title) <= 30:
            factors.append("적절한 제목 길이")
        if "?" in title:
            factors.append("호기심 유발 제목")
        if any(e in title for e in ["ㅋㅋ", "ㅎㅎ", "!!"]):
            factors.append("감정적 제목")

        # 본문 분석
        if len(content) >= 500:
            factors.append("충분한 본문 길이")
        if post_data.get("image_count", 0) >= 2:
            factors.append("다수의 이미지")
        if "경험" in content or "해봤" in content:
            factors.append("실제 경험 공유")

        return factors

    def _calculate_reference_score(self, post: PopularPost) -> float:
        """참고 점수 계산"""
        score = 50.0

        # 조회수 기반
        if post.view_count >= 1000:
            score += 20
        elif post.view_count >= 500:
            score += 10

        # 댓글수 기반
        if post.comment_count >= 50:
            score += 15
        elif post.comment_count >= 20:
            score += 10

        # 좋아요 기반
        if post.like_count >= 50:
            score += 15
        elif post.like_count >= 20:
            score += 10

        return min(score, 100)

    async def analyze_patterns(
        self,
        db: AsyncSession,
        user_id: str,
        cafe_id: Optional[str] = None,
        period: str = "week"
    ) -> PopularPostPattern:
        """인기글 패턴 분석"""
        days = 7 if period == "week" else 30
        start_date = datetime.utcnow() - timedelta(days=days)

        query = select(PopularPost).where(
            and_(
                PopularPost.user_id == user_id,
                PopularPost.created_at >= start_date
            )
        )

        if cafe_id:
            query = query.where(PopularPost.cafe_id == cafe_id)

        result = await db.execute(query)
        posts = list(result.scalars().all())

        if not posts:
            return None

        # 제목 패턴
        title_lengths = [len(p.title or "") for p in posts]
        title_patterns = {
            "avg_length": sum(title_lengths) / len(title_lengths),
            "common_words": self._find_common_words([p.title for p in posts]),
            "question_rate": sum(1 for p in posts if "?" in (p.title or "")) / len(posts)
        }

        # 본문 패턴
        content_patterns = {
            "avg_length": sum(p.content_length or 0 for p in posts) / len(posts),
            "avg_image_count": sum(p.image_count or 0 for p in posts) / len(posts)
        }

        # 시간 패턴
        hours = [p.posted_at.hour for p in posts if p.posted_at]
        days_of_week = [p.posted_at.weekday() for p in posts if p.posted_at]

        time_patterns = {}
        if hours:
            time_patterns["best_hour"] = max(set(hours), key=hours.count)
        if days_of_week:
            time_patterns["best_day"] = max(set(days_of_week), key=days_of_week.count)

        # 성공 요인 집계
        all_factors = []
        for p in posts:
            all_factors.extend(p.success_factors or [])

        success_factors = self._count_factors(all_factors)

        pattern = PopularPostPattern(
            id=str(uuid.uuid4()),
            user_id=user_id,
            cafe_id=cafe_id,
            analysis_period=period,
            title_patterns=title_patterns,
            content_patterns=content_patterns,
            time_patterns=time_patterns,
            success_factors=success_factors,
            sample_count=len(posts)
        )

        db.add(pattern)
        await db.commit()
        await db.refresh(pattern)
        return pattern

    def _find_common_words(self, titles: List[str]) -> List[str]:
        """자주 등장하는 단어 찾기"""
        import re
        word_freq = {}

        for title in titles:
            if not title:
                continue
            words = re.findall(r'[가-힣]{2,}', title)
            for word in words:
                word_freq[word] = word_freq.get(word, 0) + 1

        sorted_words = sorted(
            word_freq.items(), key=lambda x: x[1], reverse=True
        )
        return [w[0] for w in sorted_words[:10]]

    def _count_factors(self, factors: List[str]) -> Dict[str, int]:
        """요인 집계"""
        counts = {}
        for f in factors:
            counts[f] = counts.get(f, 0) + 1
        return counts


class EngagementService:
    """팔로우/좋아요 활동 서비스"""

    async def create_schedule(
        self,
        db: AsyncSession,
        user_id: str,
        name: str,
        activity_types: List[str],
        target_cafes: Optional[List[str]] = None,
        target_boards: Optional[List[str]] = None,
        target_keywords: Optional[List[str]] = None,
        daily_like_limit: int = 30,
        daily_save_limit: int = 10,
        daily_follow_limit: int = 5,
        min_interval: int = 60,
        max_interval: int = 300,
        working_hours: Optional[Dict[str, str]] = None,
        working_days: Optional[List[int]] = None
    ) -> EngagementSchedule:
        """활동 스케줄 생성"""
        schedule = EngagementSchedule(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            activity_types=activity_types,
            target_cafes=target_cafes,
            target_boards=target_boards,
            target_keywords=target_keywords,
            daily_like_limit=daily_like_limit,
            daily_save_limit=daily_save_limit,
            daily_follow_limit=daily_follow_limit,
            min_interval_seconds=min_interval,
            max_interval_seconds=max_interval,
            working_hours=working_hours or {"start": "09:00", "end": "22:00"},
            working_days=working_days or [1, 2, 3, 4, 5, 6, 7]
        )
        db.add(schedule)
        await db.commit()
        await db.refresh(schedule)
        return schedule

    async def record_activity(
        self,
        db: AsyncSession,
        user_id: str,
        activity_type: str,
        target_type: str,
        target_id: str,
        target_url: Optional[str] = None,
        target_author: Optional[str] = None,
        account_id: Optional[str] = None,
        cafe_id: Optional[str] = None,
        is_success: bool = True,
        error_message: Optional[str] = None
    ) -> EngagementActivity:
        """활동 기록"""
        activity = EngagementActivity(
            id=str(uuid.uuid4()),
            user_id=user_id,
            account_id=account_id,
            cafe_id=cafe_id,
            activity_type=activity_type,
            target_type=target_type,
            target_id=target_id,
            target_url=target_url,
            target_author=target_author,
            is_success=is_success,
            error_message=error_message,
            executed_at=datetime.utcnow()
        )
        db.add(activity)

        # 스케줄 통계 업데이트
        result = await db.execute(
            select(EngagementSchedule).where(
                and_(
                    EngagementSchedule.user_id == user_id,
                    EngagementSchedule.is_active == True
                )
            )
        )
        schedules = list(result.scalars().all())

        for schedule in schedules:
            if activity_type == EngagementType.LIKE.value:
                schedule.total_likes += 1
            elif activity_type == EngagementType.SAVE.value:
                schedule.total_saves += 1
            elif activity_type == EngagementType.FOLLOW.value:
                schedule.total_follows += 1

        await db.commit()
        await db.refresh(activity)
        return activity

    async def get_today_activity_count(
        self,
        db: AsyncSession,
        user_id: str,
        activity_type: str
    ) -> int:
        """오늘 활동 수 조회"""
        today = date.today()
        start_of_day = datetime.combine(today, datetime.min.time())

        result = await db.execute(
            select(func.count(EngagementActivity.id)).where(
                and_(
                    EngagementActivity.user_id == user_id,
                    EngagementActivity.activity_type == activity_type,
                    EngagementActivity.executed_at >= start_of_day,
                    EngagementActivity.is_success == True
                )
            )
        )
        return result.scalar() or 0

    async def can_perform_activity(
        self,
        db: AsyncSession,
        schedule: EngagementSchedule,
        activity_type: str
    ) -> bool:
        """활동 수행 가능 여부"""
        # 일일 한도 확인
        today_count = await self.get_today_activity_count(
            db, schedule.user_id, activity_type
        )

        if activity_type == EngagementType.LIKE.value:
            if today_count >= schedule.daily_like_limit:
                return False
        elif activity_type == EngagementType.SAVE.value:
            if today_count >= schedule.daily_save_limit:
                return False
        elif activity_type == EngagementType.FOLLOW.value:
            if today_count >= schedule.daily_follow_limit:
                return False

        # 업무 시간 확인
        now = datetime.now()
        working_hours = schedule.working_hours or {}
        start_hour = int(working_hours.get("start", "09:00").split(":")[0])
        end_hour = int(working_hours.get("end", "22:00").split(":")[0])

        if not (start_hour <= now.hour < end_hour):
            return False

        # 업무일 확인
        working_days = schedule.working_days or [1, 2, 3, 4, 5, 6, 7]
        if now.isoweekday() not in working_days:
            return False

        return True

    async def get_activity_stats(
        self,
        db: AsyncSession,
        user_id: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """활동 통계"""
        start_date = datetime.utcnow() - timedelta(days=days)

        result = await db.execute(
            select(EngagementActivity).where(
                and_(
                    EngagementActivity.user_id == user_id,
                    EngagementActivity.executed_at >= start_date
                )
            )
        )
        activities = list(result.scalars().all())

        stats = {
            "total": len(activities),
            "success": sum(1 for a in activities if a.is_success),
            "by_type": {},
            "by_day": {}
        }

        for activity in activities:
            # 유형별
            t = activity.activity_type
            if t not in stats["by_type"]:
                stats["by_type"][t] = 0
            stats["by_type"][t] += 1

            # 일별
            day = activity.executed_at.date().isoformat()
            if day not in stats["by_day"]:
                stats["by_day"][day] = 0
            stats["by_day"][day] += 1

        return stats


# 싱글톤 인스턴스
board_targeting = BoardTargetingService()
reply_automation = ReplyAutomationService()
popular_post_analysis = PopularPostAnalysisService()
engagement_service = EngagementService()
