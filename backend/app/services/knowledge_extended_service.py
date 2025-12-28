"""
지식인 확장 서비스
- 채택률 추적
- 경쟁 답변 분석
- 질문자 분석
- 내공 우선순위
"""

import uuid
import aiohttp
import re
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.knowledge_extended import (
    AnswerAdoption, CompetitorAnswer, AnswerStrategy,
    AnswerImage, ImageTemplate, QuestionerProfile,
    RewardPriorityRule, AnswerPerformance,
    AdoptionStatus, QuestionerType
)
from app.models.knowledge import KnowledgeQuestion, KnowledgeAnswer


class AdoptionTrackerService:
    """채택률 추적 서비스"""

    async def create_adoption_record(
        self,
        db: AsyncSession,
        user_id: str,
        answer_id: str,
        question_id: str
    ) -> AnswerAdoption:
        """채택 추적 레코드 생성"""
        record = AnswerAdoption(
            id=str(uuid.uuid4()),
            user_id=user_id,
            answer_id=answer_id,
            question_id=question_id,
            status=AdoptionStatus.PENDING.value
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record

    async def check_adoption(
        self,
        db: AsyncSession,
        adoption_id: str,
        is_adopted: bool,
        total_answers: int = 0,
        adoption_rank: Optional[int] = None
    ) -> AnswerAdoption:
        """채택 상태 확인/업데이트"""
        result = await db.execute(
            select(AnswerAdoption).where(AnswerAdoption.id == adoption_id)
        )
        record = result.scalar_one_or_none()

        if record:
            record.checked_at = datetime.utcnow()
            record.check_count += 1
            record.total_answers = total_answers

            if is_adopted:
                record.status = AdoptionStatus.ADOPTED.value
                record.is_adopted = True
                record.adopted_at = datetime.utcnow()
                record.adoption_rank = adoption_rank
            else:
                # 질문 마감 여부 확인 필요
                pass

            await db.commit()
            await db.refresh(record)

        return record

    async def mark_question_closed(
        self,
        db: AsyncSession,
        question_id: str
    ):
        """질문 마감 처리"""
        result = await db.execute(
            select(AnswerAdoption).where(
                and_(
                    AnswerAdoption.question_id == question_id,
                    AnswerAdoption.status == AdoptionStatus.PENDING.value
                )
            )
        )
        records = list(result.scalars().all())

        for record in records:
            if not record.is_adopted:
                record.status = AdoptionStatus.NOT_ADOPTED.value
            record.question_closed = True
            record.question_closed_at = datetime.utcnow()

        await db.commit()

    async def get_adoption_stats(
        self,
        db: AsyncSession,
        user_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """채택 통계"""
        start_date = datetime.utcnow() - timedelta(days=days)

        result = await db.execute(
            select(AnswerAdoption).where(
                and_(
                    AnswerAdoption.user_id == user_id,
                    AnswerAdoption.created_at >= start_date
                )
            )
        )
        records = list(result.scalars().all())

        total = len(records)
        adopted = sum(1 for r in records if r.is_adopted)
        pending = sum(1 for r in records if r.status == AdoptionStatus.PENDING.value)

        # 평균 채택 시간
        adopted_records = [r for r in records if r.is_adopted and r.adopted_at]
        avg_adoption_time = None
        if adopted_records:
            times = [
                (r.adopted_at - r.created_at).total_seconds() / 3600
                for r in adopted_records
            ]
            avg_adoption_time = sum(times) / len(times)

        return {
            "total_answers": total,
            "adopted": adopted,
            "pending": pending,
            "not_adopted": total - adopted - pending,
            "adoption_rate": round(adopted / total * 100, 1) if total > 0 else 0,
            "avg_adoption_hours": round(avg_adoption_time, 1) if avg_adoption_time else None
        }


class CompetitorAnalysisService:
    """경쟁 답변 분석 서비스"""

    async def analyze_competitor_answers(
        self,
        db: AsyncSession,
        user_id: str,
        question_id: str,
        answers: List[Dict[str, Any]]
    ) -> List[CompetitorAnswer]:
        """경쟁 답변 분석 및 저장"""
        competitor_answers = []

        for answer_data in answers:
            comp = CompetitorAnswer(
                id=str(uuid.uuid4()),
                user_id=user_id,
                question_id=question_id,
                answer_id=answer_data.get("answer_id"),
                author_name=answer_data.get("author_name"),
                author_id=answer_data.get("author_id"),
                author_level=answer_data.get("author_level"),
                content=answer_data.get("content"),
                content_length=len(answer_data.get("content", "")),
                has_image=answer_data.get("has_image", False),
                has_link=answer_data.get("has_link", False),
                image_count=answer_data.get("image_count", 0),
                is_adopted=answer_data.get("is_adopted", False),
                like_count=answer_data.get("like_count", 0)
            )

            # AI 분석 (간단한 휴리스틱)
            content = answer_data.get("content", "")
            comp.quality_score = self._calculate_quality_score(content, answer_data)
            comp.tone = self._detect_tone(content)
            comp.strengths = self._analyze_strengths(content, answer_data)
            comp.weaknesses = self._analyze_weaknesses(content, answer_data)
            comp.key_points = self._extract_key_points(content)

            db.add(comp)
            competitor_answers.append(comp)

        await db.commit()
        return competitor_answers

    def _calculate_quality_score(
        self,
        content: str,
        data: Dict[str, Any]
    ) -> float:
        """품질 점수 계산"""
        score = 50.0  # 기본 점수

        # 길이 점수
        length = len(content)
        if length > 500:
            score += 10
        elif length > 200:
            score += 5

        # 구조화 점수
        if "\n" in content:
            score += 5
        if any(c in content for c in ["1.", "2.", "①", "②", "-", "•"]):
            score += 10

        # 이미지 점수
        if data.get("has_image"):
            score += 10

        # 링크 점수
        if data.get("has_link"):
            score += 5

        # 채택 여부
        if data.get("is_adopted"):
            score += 20

        return min(score, 100)

    def _detect_tone(self, content: str) -> str:
        """어조 감지"""
        formal_words = ["합니다", "입니다", "드립니다", "습니다"]
        casual_words = ["해요", "에요", "요", "ㅋㅋ", "ㅎㅎ"]
        empathetic_words = ["걱정", "힘드", "이해", "공감", "마음"]

        formal_count = sum(1 for w in formal_words if w in content)
        casual_count = sum(1 for w in casual_words if w in content)
        empathetic_count = sum(1 for w in empathetic_words if w in content)

        if empathetic_count >= 2:
            return "empathetic"
        elif formal_count > casual_count:
            return "professional"
        elif casual_count > formal_count:
            return "casual"
        return "neutral"

    def _analyze_strengths(
        self,
        content: str,
        data: Dict[str, Any]
    ) -> List[str]:
        """강점 분석"""
        strengths = []

        if len(content) > 500:
            strengths.append("상세한 설명")
        if data.get("has_image"):
            strengths.append("시각 자료 포함")
        if any(c in content for c in ["1.", "2.", "①", "②"]):
            strengths.append("구조화된 답변")
        if "경험" in content or "해봤" in content:
            strengths.append("실제 경험 공유")
        if data.get("author_level") and "전문가" in data.get("author_level", ""):
            strengths.append("전문가 답변")

        return strengths

    def _analyze_weaknesses(
        self,
        content: str,
        data: Dict[str, Any]
    ) -> List[str]:
        """약점 분석"""
        weaknesses = []

        if len(content) < 100:
            weaknesses.append("너무 짧은 답변")
        if not data.get("has_image") and len(content) > 300:
            weaknesses.append("이미지 없음")
        if "광고" in content or "홍보" in content:
            weaknesses.append("광고성 느낌")

        return weaknesses

    def _extract_key_points(self, content: str) -> List[str]:
        """핵심 포인트 추출"""
        # 문장 분리
        sentences = re.split(r'[.!?]\s+', content)
        key_points = []

        for sentence in sentences[:5]:  # 처음 5개 문장만
            if len(sentence) > 20 and len(sentence) < 100:
                key_points.append(sentence.strip())

        return key_points[:3]  # 최대 3개

    async def create_strategy(
        self,
        db: AsyncSession,
        user_id: str,
        question_id: str
    ) -> AnswerStrategy:
        """답변 전략 생성"""
        # 경쟁 답변 조회
        result = await db.execute(
            select(CompetitorAnswer).where(
                and_(
                    CompetitorAnswer.user_id == user_id,
                    CompetitorAnswer.question_id == question_id
                )
            )
        )
        competitors = list(result.scalars().all())

        strategy = AnswerStrategy(
            id=str(uuid.uuid4()),
            user_id=user_id,
            question_id=question_id,
            competitor_count=len(competitors)
        )

        if competitors:
            # 평균 분석
            strategy.avg_content_length = int(
                sum(c.content_length or 0 for c in competitors) / len(competitors)
            )
            strategy.image_usage_rate = sum(
                1 for c in competitors if c.has_image
            ) / len(competitors)
            strategy.link_usage_rate = sum(
                1 for c in competitors if c.has_link
            ) / len(competitors)

            # 추천 전략
            strategy.recommended_length = max(strategy.avg_content_length + 100, 300)
            strategy.recommended_tone = "professional"
            strategy.recommended_structure = ["인사", "공감", "정보제공", "추가조언", "마무리"]

            # 이미지 포함 결정
            strategy.include_image = strategy.image_usage_rate < 0.5  # 경쟁자가 안 쓰면 차별화

            # 차별화 포인트
            diff_points = []
            if strategy.image_usage_rate < 0.3:
                diff_points.append("이미지 추가로 시각적 차별화")
            if strategy.avg_content_length < 300:
                diff_points.append("더 상세한 설명 제공")

            adopted_competitors = [c for c in competitors if c.is_adopted]
            if not adopted_competitors:
                diff_points.append("빠른 응답으로 선점")

            strategy.differentiation_points = diff_points

            # 채택 확률 예측
            base_prob = 0.3
            if len(competitors) == 0:
                base_prob = 0.8
            elif len(competitors) < 3:
                base_prob = 0.5

            if not adopted_competitors:
                base_prob += 0.2

            strategy.adoption_probability = min(base_prob, 0.95)

        db.add(strategy)
        await db.commit()
        await db.refresh(strategy)

        return strategy


class QuestionerAnalysisService:
    """질문자 분석 서비스"""

    async def analyze_questioner(
        self,
        db: AsyncSession,
        user_id: str,
        questioner_id: str,
        questioner_name: str,
        question_data: Dict[str, Any]
    ) -> QuestionerProfile:
        """질문자 분석"""
        # 기존 프로필 조회
        result = await db.execute(
            select(QuestionerProfile).where(
                and_(
                    QuestionerProfile.user_id == user_id,
                    QuestionerProfile.questioner_id == questioner_id
                )
            )
        )
        profile = result.scalar_one_or_none()

        if not profile:
            profile = QuestionerProfile(
                id=str(uuid.uuid4()),
                user_id=user_id,
                questioner_id=questioner_id,
                questioner_name=questioner_name,
                first_seen_at=datetime.utcnow()
            )
            db.add(profile)

        # 질문 카운트 증가
        profile.total_questions += 1
        profile.last_seen_at = datetime.utcnow()

        # 카테고리 업데이트
        category = question_data.get("category", "기타")
        categories = profile.question_categories or {}
        categories[category] = categories.get(category, 0) + 1
        profile.question_categories = categories

        # 내공 평균 업데이트
        reward = question_data.get("reward_points", 0)
        if profile.avg_reward_points:
            profile.avg_reward_points = (
                profile.avg_reward_points + reward
            ) / 2
        else:
            profile.avg_reward_points = reward

        # 질문자 유형 분류
        profile.questioner_type = self._classify_questioner(profile, question_data)
        profile.is_potential_customer = (
            profile.questioner_type == QuestionerType.POTENTIAL_CUSTOMER.value
        )

        # 고객 점수 계산
        profile.customer_score = self._calculate_customer_score(profile, question_data)

        # 관심사 추출
        interests = self._extract_interests(question_data.get("content", ""))
        if interests:
            profile.interests = list(set(
                (profile.interests or []) + interests
            ))[:10]

        # 우려사항 추출
        concerns = self._extract_concerns(question_data.get("content", ""))
        if concerns:
            profile.concerns = list(set(
                (profile.concerns or []) + concerns
            ))[:10]

        await db.commit()
        await db.refresh(profile)

        return profile

    def _classify_questioner(
        self,
        profile: QuestionerProfile,
        question_data: Dict[str, Any]
    ) -> str:
        """질문자 유형 분류"""
        content = question_data.get("content", "").lower()

        # 스패머 감지
        spam_indicators = ["광고", "홍보", "클릭", "무료", "이벤트"]
        if sum(1 for w in spam_indicators if w in content) >= 2:
            return QuestionerType.SPAMMER.value

        # 경쟁사 감지
        competitor_indicators = ["우리병원", "저희", "시술해드", "치료해드"]
        if any(w in content for w in competitor_indicators):
            return QuestionerType.COMPETITOR.value

        # 잠재 고객 감지
        customer_indicators = [
            "추천", "어디", "좋은곳", "병원", "가격", "비용",
            "효과", "부작용", "후기", "경험"
        ]
        if sum(1 for w in customer_indicators if w in content) >= 2:
            return QuestionerType.POTENTIAL_CUSTOMER.value

        return QuestionerType.INFORMATION_SEEKER.value

    def _calculate_customer_score(
        self,
        profile: QuestionerProfile,
        question_data: Dict[str, Any]
    ) -> float:
        """고객 점수 계산 (0-100)"""
        score = 50.0

        # 카테고리 기반
        categories = profile.question_categories or {}
        medical_categories = ["의료", "건강", "병원", "피부", "성형"]
        for cat in medical_categories:
            if cat in str(categories):
                score += 10
                break

        # 내공 기반
        if profile.avg_reward_points:
            if profile.avg_reward_points >= 100:
                score += 15
            elif profile.avg_reward_points >= 50:
                score += 10

        # 질문 빈도
        if profile.total_questions >= 3:
            score += 5

        # 질문 내용 분석
        content = question_data.get("content", "").lower()

        purchase_intent = ["가격", "비용", "얼마", "예약", "상담"]
        if any(w in content for w in purchase_intent):
            score += 15

        location_intent = ["서울", "강남", "부산", "근처", "가까운"]
        if any(w in content for w in location_intent):
            score += 10

        return min(score, 100)

    def _extract_interests(self, content: str) -> List[str]:
        """관심사 추출"""
        interests = []
        interest_patterns = {
            "피부관리": ["피부", "여드름", "모공", "주름", "탄력"],
            "성형": ["코", "눈", "턱", "윤곽", "지방"],
            "탈모": ["탈모", "머리카락", "두피"],
            "다이어트": ["살", "체중", "다이어트", "지방"],
            "치과": ["치아", "이빨", "충치", "임플란트"]
        }

        for interest, keywords in interest_patterns.items():
            if any(k in content for k in keywords):
                interests.append(interest)

        return interests

    def _extract_concerns(self, content: str) -> List[str]:
        """우려사항 추출"""
        concerns = []
        concern_patterns = {
            "가격": ["비싸", "가격", "비용", "돈"],
            "부작용": ["부작용", "위험", "안전", "부담"],
            "효과": ["효과", "결과", "개선"],
            "통증": ["아프", "통증", "마취"],
            "시간": ["시간", "기간", "얼마나 걸"]
        }

        for concern, keywords in concern_patterns.items():
            if any(k in content for k in keywords):
                concerns.append(concern)

        return concerns


class RewardPriorityService:
    """내공 우선순위 서비스"""

    async def create_rule(
        self,
        db: AsyncSession,
        user_id: str,
        name: str,
        min_reward: int = 0,
        max_reward: Optional[int] = None,
        priority_boost: float = 1.0,
        categories: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        exclude_keywords: Optional[List[str]] = None,
        max_question_age_hours: Optional[int] = None,
        max_existing_answers: Optional[int] = None
    ) -> RewardPriorityRule:
        """우선순위 규칙 생성"""
        rule = RewardPriorityRule(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            min_reward_points=min_reward,
            max_reward_points=max_reward,
            priority_boost=priority_boost,
            categories=categories,
            keywords=keywords,
            exclude_keywords=exclude_keywords,
            max_question_age_hours=max_question_age_hours,
            max_existing_answers=max_existing_answers
        )
        db.add(rule)
        await db.commit()
        await db.refresh(rule)
        return rule

    async def get_rules(
        self,
        db: AsyncSession,
        user_id: str,
        is_active: bool = True
    ) -> List[RewardPriorityRule]:
        """규칙 목록 조회"""
        query = select(RewardPriorityRule).where(
            and_(
                RewardPriorityRule.user_id == user_id,
                RewardPriorityRule.is_active == is_active
            )
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def calculate_priority(
        self,
        db: AsyncSession,
        user_id: str,
        question: KnowledgeQuestion
    ) -> float:
        """질문 우선순위 계산"""
        rules = await self.get_rules(db, user_id)

        base_priority = 1.0

        # 기본 내공 기반 우선순위
        reward = question.reward_points or 0
        if reward >= 100:
            base_priority *= 1.5
        elif reward >= 50:
            base_priority *= 1.3
        elif reward >= 30:
            base_priority *= 1.1

        # 규칙 적용
        for rule in rules:
            if self._matches_rule(rule, question):
                base_priority *= rule.priority_boost

        return round(base_priority, 2)

    def _matches_rule(
        self,
        rule: RewardPriorityRule,
        question: KnowledgeQuestion
    ) -> bool:
        """규칙 매칭 확인"""
        reward = question.reward_points or 0

        # 내공 범위 확인
        if reward < rule.min_reward_points:
            return False
        if rule.max_reward_points and reward > rule.max_reward_points:
            return False

        # 카테고리 확인
        if rule.categories:
            if not any(c in (question.category or "") for c in rule.categories):
                return False

        # 키워드 확인
        content = f"{question.title or ''} {question.content or ''}"
        if rule.keywords:
            if not any(k in content for k in rule.keywords):
                return False

        # 제외 키워드 확인
        if rule.exclude_keywords:
            if any(k in content for k in rule.exclude_keywords):
                return False

        # 질문 경과 시간 확인
        if rule.max_question_age_hours:
            age = (datetime.utcnow() - question.created_at).total_seconds() / 3600
            if age > rule.max_question_age_hours:
                return False

        # 기존 답변 수 확인
        if rule.max_existing_answers:
            if (question.answer_count or 0) > rule.max_existing_answers:
                return False

        return True


# 싱글톤 인스턴스
adoption_tracker = AdoptionTrackerService()
competitor_analysis = CompetitorAnalysisService()
questioner_analysis = QuestionerAnalysisService()
reward_priority = RewardPriorityService()
