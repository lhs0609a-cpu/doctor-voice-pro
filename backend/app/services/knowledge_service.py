"""
네이버 지식인 자동 답변 서비스
"""
import re
import json
import httpx
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import (
    KnowledgeKeyword, KnowledgeQuestion, KnowledgeAnswer, AnswerTemplate,
    AutoAnswerSetting, KnowledgeStats,
    QuestionStatus, AnswerStatus, AnswerTone, Urgency
)
from app.models.doctor_profile import DoctorProfile
from app.services.ai_service import AIService


class KnowledgeService:
    """지식인 답변 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.ai_service = AIService()

    # ==================== 키워드 관리 ====================

    async def create_keyword(
        self,
        user_id: str,
        keyword: str,
        category: Optional[str] = None,
        sub_category: Optional[str] = None,
        priority: int = 1
    ) -> KnowledgeKeyword:
        """모니터링 키워드 추가"""
        kw = KnowledgeKeyword(
            user_id=user_id,
            keyword=keyword,
            category=category,
            sub_category=sub_category,
            priority=priority
        )
        self.db.add(kw)
        await self.db.commit()
        await self.db.refresh(kw)
        return kw

    async def get_keywords(
        self,
        user_id: str,
        is_active: Optional[bool] = None
    ) -> List[KnowledgeKeyword]:
        """키워드 목록 조회"""
        query = select(KnowledgeKeyword).where(KnowledgeKeyword.user_id == user_id)
        if is_active is not None:
            query = query.where(KnowledgeKeyword.is_active == is_active)
        query = query.order_by(desc(KnowledgeKeyword.priority), KnowledgeKeyword.created_at)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_keyword(
        self,
        keyword_id: str,
        user_id: str,
        **updates
    ) -> Optional[KnowledgeKeyword]:
        """키워드 수정"""
        query = select(KnowledgeKeyword).where(
            KnowledgeKeyword.id == keyword_id,
            KnowledgeKeyword.user_id == user_id
        )
        result = await self.db.execute(query)
        kw = result.scalar_one_or_none()

        if kw:
            for key, value in updates.items():
                if hasattr(kw, key):
                    setattr(kw, key, value)
            await self.db.commit()
            await self.db.refresh(kw)
        return kw

    async def delete_keyword(self, keyword_id: str, user_id: str) -> bool:
        """키워드 삭제"""
        query = select(KnowledgeKeyword).where(
            KnowledgeKeyword.id == keyword_id,
            KnowledgeKeyword.user_id == user_id
        )
        result = await self.db.execute(query)
        kw = result.scalar_one_or_none()

        if kw:
            await self.db.delete(kw)
            await self.db.commit()
            return True
        return False

    # ==================== 질문 수집 ====================

    async def collect_questions(
        self,
        user_id: str,
        keywords: Optional[List[str]] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """질문 수집 (시뮬레이션 - 실제로는 크롤링 필요)"""
        # 사용자의 활성 키워드 가져오기
        if not keywords:
            kw_list = await self.get_keywords(user_id, is_active=True)
            keywords = [kw.keyword for kw in kw_list]

        if not keywords:
            return {"collected": 0, "message": "모니터링 키워드가 없습니다."}

        # 실제 구현에서는 여기서 네이버 지식인 API/크롤링 수행
        # 현재는 시뮬레이션 데이터 반환
        collected = 0
        simulated_questions = self._generate_simulated_questions(keywords, limit)

        for q_data in simulated_questions:
            # 중복 체크
            existing = await self.db.execute(
                select(KnowledgeQuestion).where(
                    KnowledgeQuestion.naver_question_id == q_data["naver_question_id"]
                )
            )
            if existing.scalar_one_or_none():
                continue

            # 관련성 분석
            analysis = await self._analyze_question(q_data, keywords)

            question = KnowledgeQuestion(
                user_id=user_id,
                naver_question_id=q_data["naver_question_id"],
                title=q_data["title"],
                content=q_data["content"],
                category=q_data.get("category"),
                url=q_data.get("url"),
                author_name=q_data.get("author_name"),
                view_count=q_data.get("view_count", 0),
                answer_count=q_data.get("answer_count", 0),
                reward_points=q_data.get("reward_points", 0),
                matched_keywords=analysis["matched_keywords"],
                relevance_score=analysis["relevance_score"],
                urgency=analysis["urgency"],
                key_points=analysis.get("key_points"),
                question_date=q_data.get("question_date"),
                collected_at=datetime.utcnow()
            )
            self.db.add(question)
            collected += 1

        await self.db.commit()

        return {
            "collected": collected,
            "keywords_used": keywords,
            "message": f"{collected}개의 새로운 질문을 수집했습니다."
        }

    def _generate_simulated_questions(
        self,
        keywords: List[str],
        limit: int
    ) -> List[Dict[str, Any]]:
        """시뮬레이션용 질문 생성"""
        import random
        import uuid

        templates = [
            "{keyword} 추천해주세요",
            "{keyword} 효과가 어떤가요?",
            "{keyword} 부작용이 있나요?",
            "{keyword} 비용이 얼마인가요?",
            "{keyword} 후기 알려주세요",
            "{keyword} vs 다른 시술 뭐가 좋아요?",
            "{keyword} 유명한 곳 있나요?",
            "{keyword} 경험 있으신 분 계신가요?",
        ]

        questions = []
        for i in range(min(limit, len(keywords) * 3)):
            keyword = random.choice(keywords)
            template = random.choice(templates)

            questions.append({
                "naver_question_id": f"sim_{uuid.uuid4().hex[:12]}",
                "title": template.format(keyword=keyword),
                "content": f"{keyword}에 대해 궁금합니다. 자세한 정보 알려주세요.",
                "category": "의료, 건강",
                "url": f"https://kin.naver.com/qna/detail.naver?d1id=7&dirId=70101&docId={i}",
                "author_name": f"지식인{random.randint(1, 100)}",
                "view_count": random.randint(10, 500),
                "answer_count": random.randint(0, 5),
                "reward_points": random.choice([0, 10, 30, 50, 100]),
                "question_date": datetime.utcnow() - timedelta(hours=random.randint(1, 48))
            })

        return questions

    async def _analyze_question(
        self,
        question_data: Dict[str, Any],
        keywords: List[str]
    ) -> Dict[str, Any]:
        """질문 분석"""
        title = question_data.get("title", "")
        content = question_data.get("content", "")
        full_text = f"{title} {content}".lower()

        # 매칭 키워드 찾기
        matched = [kw for kw in keywords if kw.lower() in full_text]

        # 관련성 점수 계산
        relevance_score = min(100, len(matched) * 30 + 20)

        # 긴급도 판단
        urgent_keywords = ["급해요", "빨리", "오늘", "내일", "당장", "바로"]
        is_urgent = any(uk in full_text for uk in urgent_keywords)

        return {
            "matched_keywords": matched,
            "relevance_score": relevance_score,
            "urgency": Urgency.HIGH if is_urgent else Urgency.MEDIUM,
            "key_points": matched[:5]
        }

    # ==================== 질문 조회 ====================

    async def get_questions(
        self,
        user_id: str,
        status: Optional[QuestionStatus] = None,
        min_relevance: Optional[float] = None,
        keyword: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[KnowledgeQuestion]:
        """질문 목록 조회"""
        query = select(KnowledgeQuestion).where(KnowledgeQuestion.user_id == user_id)

        if status:
            query = query.where(KnowledgeQuestion.status == status)
        if min_relevance is not None:
            query = query.where(KnowledgeQuestion.relevance_score >= min_relevance)
        if keyword:
            query = query.where(
                or_(
                    KnowledgeQuestion.title.ilike(f"%{keyword}%"),
                    KnowledgeQuestion.content.ilike(f"%{keyword}%")
                )
            )

        query = query.order_by(
            desc(KnowledgeQuestion.relevance_score),
            desc(KnowledgeQuestion.collected_at)
        ).offset(offset).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_question(self, question_id: str, user_id: str) -> Optional[KnowledgeQuestion]:
        """질문 상세 조회"""
        query = select(KnowledgeQuestion).where(
            KnowledgeQuestion.id == question_id,
            KnowledgeQuestion.user_id == user_id
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def update_question_status(
        self,
        question_id: str,
        user_id: str,
        status: QuestionStatus,
        skip_reason: Optional[str] = None
    ) -> Optional[KnowledgeQuestion]:
        """질문 상태 변경"""
        question = await self.get_question(question_id, user_id)
        if question:
            question.status = status
            if skip_reason:
                question.skip_reason = skip_reason
            await self.db.commit()
            await self.db.refresh(question)
        return question

    # ==================== 답변 생성 ====================

    async def generate_answer(
        self,
        question_id: str,
        user_id: str,
        tone: AnswerTone = AnswerTone.PROFESSIONAL,
        include_promotion: bool = True,
        blog_link: Optional[str] = None,
        place_link: Optional[str] = None,
        template_id: Optional[str] = None
    ) -> Optional[KnowledgeAnswer]:
        """AI 답변 생성"""
        question = await self.get_question(question_id, user_id)
        if not question:
            return None

        # 사용자 프로필 가져오기
        profile_query = select(DoctorProfile).where(DoctorProfile.user_id == user_id)
        profile_result = await self.db.execute(profile_query)
        profile = profile_result.scalar_one_or_none()

        # 템플릿 사용 시
        template_content = None
        if template_id:
            template_query = select(AnswerTemplate).where(
                AnswerTemplate.id == template_id,
                AnswerTemplate.user_id == user_id
            )
            template_result = await self.db.execute(template_query)
            template = template_result.scalar_one_or_none()
            if template:
                template_content = template.template_content
                template.usage_count += 1

        # AI 답변 생성
        answer_content = await self._generate_answer_with_ai(
            question=question,
            profile=profile,
            tone=tone,
            include_promotion=include_promotion,
            template_content=template_content
        )

        # 홍보 문구 생성
        promotion_text = None
        if include_promotion and profile:
            promotion_text = self._generate_promotion_text(profile, blog_link, place_link)

        # 품질 점수 계산
        quality_scores = self._calculate_quality_scores(answer_content)

        # 답변 저장
        answer = KnowledgeAnswer(
            question_id=question_id,
            user_id=user_id,
            content=answer_content,
            final_content=answer_content,
            tone=tone,
            include_promotion=include_promotion,
            promotion_text=promotion_text,
            blog_link=blog_link,
            place_link=place_link,
            quality_score=quality_scores["overall"],
            professionalism_score=quality_scores["professionalism"],
            readability_score=quality_scores["readability"],
            status=AnswerStatus.DRAFT
        )
        self.db.add(answer)

        # 질문 상태 업데이트
        question.status = QuestionStatus.REVIEWING

        await self.db.commit()
        await self.db.refresh(answer)
        return answer

    async def _generate_answer_with_ai(
        self,
        question: KnowledgeQuestion,
        profile: Optional[DoctorProfile],
        tone: AnswerTone,
        include_promotion: bool,
        template_content: Optional[str] = None
    ) -> str:
        """AI로 답변 생성"""
        tone_descriptions = {
            AnswerTone.PROFESSIONAL: "전문적이고 신뢰감 있는",
            AnswerTone.FRIENDLY: "친근하고 따뜻한",
            AnswerTone.EMPATHETIC: "공감하고 이해하는",
            AnswerTone.FORMAL: "격식있고 정중한"
        }

        profile_info = ""
        if profile:
            profile_info = f"""
[전문가 정보]
- 전문 분야: {profile.specialty or '의료'}
- 병원: {profile.hospital_name or ''}
- 경력: {profile.experience_years or ''}년
"""

        template_guide = ""
        if template_content:
            template_guide = f"""
[답변 템플릿 참고]
{template_content}

위 템플릿의 구조와 어조를 참고하여 답변을 작성하세요.
"""

        prompt = f"""당신은 의료 분야 전문가입니다. 아래 지식인 질문에 대해 {tone_descriptions.get(tone, '전문적인')} 어조로 답변을 작성해주세요.

[질문]
제목: {question.title}
내용: {question.content or '(내용 없음)'}

{profile_info}

{template_guide}

[답변 작성 가이드라인]
1. 먼저 질문자의 상황에 공감하는 인사로 시작
2. 핵심 답변을 명확하고 이해하기 쉽게 설명
3. 필요한 경우 주의사항이나 부작용 언급
4. 전문적이면서도 일반인이 이해할 수 있는 용어 사용
5. 300-500자 내외로 작성
6. 의료법에 위반되지 않도록 과장 광고 금지

답변을 작성해주세요:"""

        try:
            response = await self.ai_service.generate_text(
                prompt=prompt,
                max_tokens=1000
            )
            return response.strip()
        except Exception as e:
            # AI 실패 시 기본 답변
            return f"""안녕하세요, {question.title}에 대해 답변드립니다.

해당 내용에 대해서는 전문의와 상담을 통해 정확한 진단과 조언을 받으시는 것이 좋습니다.
개인마다 상황이 다를 수 있으므로, 직접 내원하셔서 상담받으시길 권해드립니다.

도움이 되셨길 바랍니다."""

    def _generate_promotion_text(
        self,
        profile: DoctorProfile,
        blog_link: Optional[str],
        place_link: Optional[str]
    ) -> str:
        """홍보 문구 생성"""
        parts = []

        if profile.hospital_name:
            parts.append(f"더 자세한 상담이 필요하시면 {profile.hospital_name}을 방문해주세요.")

        if blog_link:
            parts.append(f"관련 자세한 정보: {blog_link}")

        if place_link:
            parts.append(f"위치 및 예약: {place_link}")

        return "\n".join(parts) if parts else ""

    def _calculate_quality_scores(self, content: str) -> Dict[str, float]:
        """품질 점수 계산"""
        # 간단한 휴리스틱 점수 계산
        length = len(content)
        sentences = content.count('.') + content.count('?') + content.count('!')

        # 길이 점수 (200-600자가 적정)
        length_score = 100 if 200 <= length <= 600 else max(0, 100 - abs(length - 400) / 10)

        # 문장 수 점수 (5-10문장이 적정)
        sentence_score = 100 if 5 <= sentences <= 10 else max(0, 100 - abs(sentences - 7) * 10)

        # 전문성 점수 (의료 용어 포함 여부)
        medical_terms = ["증상", "치료", "진단", "상담", "전문의", "효과", "부작용"]
        term_count = sum(1 for term in medical_terms if term in content)
        professionalism = min(100, term_count * 15)

        overall = (length_score + sentence_score + professionalism) / 3

        return {
            "overall": round(overall, 1),
            "professionalism": round(professionalism, 1),
            "readability": round((length_score + sentence_score) / 2, 1)
        }

    # ==================== 답변 관리 ====================

    async def get_answers(
        self,
        user_id: str,
        status: Optional[AnswerStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[KnowledgeAnswer]:
        """답변 목록 조회"""
        query = select(KnowledgeAnswer).where(KnowledgeAnswer.user_id == user_id)

        if status:
            query = query.where(KnowledgeAnswer.status == status)

        query = query.order_by(desc(KnowledgeAnswer.created_at)).offset(offset).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_answer(self, answer_id: str, user_id: str) -> Optional[KnowledgeAnswer]:
        """답변 상세 조회"""
        query = select(KnowledgeAnswer).where(
            KnowledgeAnswer.id == answer_id,
            KnowledgeAnswer.user_id == user_id
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def update_answer(
        self,
        answer_id: str,
        user_id: str,
        edited_content: Optional[str] = None,
        **updates
    ) -> Optional[KnowledgeAnswer]:
        """답변 수정"""
        answer = await self.get_answer(answer_id, user_id)
        if not answer:
            return None

        if edited_content:
            answer.edited_content = edited_content
            answer.final_content = edited_content
            # 수정 후 품질 점수 재계산
            scores = self._calculate_quality_scores(edited_content)
            answer.quality_score = scores["overall"]
            answer.professionalism_score = scores["professionalism"]
            answer.readability_score = scores["readability"]

        for key, value in updates.items():
            if hasattr(answer, key):
                setattr(answer, key, value)

        await self.db.commit()
        await self.db.refresh(answer)
        return answer

    async def approve_answer(self, answer_id: str, user_id: str) -> Optional[KnowledgeAnswer]:
        """답변 승인"""
        answer = await self.get_answer(answer_id, user_id)
        if answer:
            answer.status = AnswerStatus.APPROVED
            await self.db.commit()
            await self.db.refresh(answer)
        return answer

    async def reject_answer(
        self,
        answer_id: str,
        user_id: str,
        reason: Optional[str] = None
    ) -> Optional[KnowledgeAnswer]:
        """답변 반려"""
        answer = await self.get_answer(answer_id, user_id)
        if answer:
            answer.status = AnswerStatus.REJECTED
            answer.rejection_reason = reason
            await self.db.commit()
            await self.db.refresh(answer)
        return answer

    async def mark_as_posted(
        self,
        answer_id: str,
        user_id: str,
        naver_answer_id: Optional[str] = None,
        naver_answer_url: Optional[str] = None
    ) -> Optional[KnowledgeAnswer]:
        """답변 등록 완료 처리"""
        answer = await self.get_answer(answer_id, user_id)
        if answer:
            answer.status = AnswerStatus.POSTED
            answer.posted_at = datetime.utcnow()
            if naver_answer_id:
                answer.naver_answer_id = naver_answer_id
            if naver_answer_url:
                answer.naver_answer_url = naver_answer_url

            # 관련 질문 상태 업데이트
            question = await self.get_question(answer.question_id, user_id)
            if question:
                question.status = QuestionStatus.ANSWERED

            await self.db.commit()
            await self.db.refresh(answer)
        return answer

    # ==================== 템플릿 관리 ====================

    async def create_template(
        self,
        user_id: str,
        name: str,
        template_content: str,
        category: Optional[str] = None,
        tone: AnswerTone = AnswerTone.PROFESSIONAL,
        question_patterns: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        variables: Optional[List[Dict]] = None
    ) -> AnswerTemplate:
        """템플릿 생성"""
        template = AnswerTemplate(
            user_id=user_id,
            name=name,
            template_content=template_content,
            category=category,
            tone=tone,
            question_patterns=question_patterns,
            keywords=keywords,
            variables=variables
        )
        self.db.add(template)
        await self.db.commit()
        await self.db.refresh(template)
        return template

    async def get_templates(
        self,
        user_id: str,
        category: Optional[str] = None,
        is_active: bool = True
    ) -> List[AnswerTemplate]:
        """템플릿 목록 조회"""
        query = select(AnswerTemplate).where(
            AnswerTemplate.user_id == user_id,
            AnswerTemplate.is_active == is_active
        )
        if category:
            query = query.where(AnswerTemplate.category == category)

        query = query.order_by(desc(AnswerTemplate.usage_count), AnswerTemplate.created_at)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_template(
        self,
        template_id: str,
        user_id: str,
        **updates
    ) -> Optional[AnswerTemplate]:
        """템플릿 수정"""
        query = select(AnswerTemplate).where(
            AnswerTemplate.id == template_id,
            AnswerTemplate.user_id == user_id
        )
        result = await self.db.execute(query)
        template = result.scalar_one_or_none()

        if template:
            for key, value in updates.items():
                if hasattr(template, key):
                    setattr(template, key, value)
            await self.db.commit()
            await self.db.refresh(template)
        return template

    async def delete_template(self, template_id: str, user_id: str) -> bool:
        """템플릿 삭제"""
        query = select(AnswerTemplate).where(
            AnswerTemplate.id == template_id,
            AnswerTemplate.user_id == user_id
        )
        result = await self.db.execute(query)
        template = result.scalar_one_or_none()

        if template:
            await self.db.delete(template)
            await self.db.commit()
            return True
        return False

    # ==================== 설정 관리 ====================

    async def get_settings(self, user_id: str) -> Optional[AutoAnswerSetting]:
        """자동 답변 설정 조회"""
        query = select(AutoAnswerSetting).where(AutoAnswerSetting.user_id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def update_settings(self, user_id: str, **updates) -> AutoAnswerSetting:
        """자동 답변 설정 업데이트"""
        settings = await self.get_settings(user_id)

        if not settings:
            settings = AutoAnswerSetting(user_id=user_id)
            self.db.add(settings)

        for key, value in updates.items():
            if hasattr(settings, key):
                setattr(settings, key, value)

        await self.db.commit()
        await self.db.refresh(settings)
        return settings

    # ==================== 통계 ====================

    async def get_dashboard_stats(self, user_id: str) -> Dict[str, Any]:
        """대시보드 통계"""
        today = datetime.utcnow().date()
        week_ago = today - timedelta(days=7)

        # 오늘 수집된 질문
        today_questions = await self.db.execute(
            select(func.count(KnowledgeQuestion.id)).where(
                KnowledgeQuestion.user_id == user_id,
                func.date(KnowledgeQuestion.collected_at) == today
            )
        )
        today_collected = today_questions.scalar() or 0

        # 대기 중인 질문
        pending = await self.db.execute(
            select(func.count(KnowledgeQuestion.id)).where(
                KnowledgeQuestion.user_id == user_id,
                KnowledgeQuestion.status == QuestionStatus.NEW
            )
        )
        pending_count = pending.scalar() or 0

        # 이번 주 답변 수
        week_answers = await self.db.execute(
            select(func.count(KnowledgeAnswer.id)).where(
                KnowledgeAnswer.user_id == user_id,
                func.date(KnowledgeAnswer.created_at) >= week_ago
            )
        )
        week_answered = week_answers.scalar() or 0

        # 채택된 답변 수
        chosen = await self.db.execute(
            select(func.count(KnowledgeAnswer.id)).where(
                KnowledgeAnswer.user_id == user_id,
                KnowledgeAnswer.is_chosen == True
            )
        )
        chosen_count = chosen.scalar() or 0

        # 초안 대기 답변
        drafts = await self.db.execute(
            select(func.count(KnowledgeAnswer.id)).where(
                KnowledgeAnswer.user_id == user_id,
                KnowledgeAnswer.status == AnswerStatus.DRAFT
            )
        )
        draft_count = drafts.scalar() or 0

        # 고관련성 질문 (70점 이상)
        high_relevance = await self.db.execute(
            select(func.count(KnowledgeQuestion.id)).where(
                KnowledgeQuestion.user_id == user_id,
                KnowledgeQuestion.status == QuestionStatus.NEW,
                KnowledgeQuestion.relevance_score >= 70
            )
        )
        high_relevance_count = high_relevance.scalar() or 0

        return {
            "today_collected": today_collected,
            "pending_questions": pending_count,
            "high_relevance_questions": high_relevance_count,
            "draft_answers": draft_count,
            "week_answered": week_answered,
            "total_chosen": chosen_count,
            "summary": {
                "date": today.isoformat(),
                "status": "active"
            }
        }

    async def get_top_questions(
        self,
        user_id: str,
        limit: int = 5
    ) -> List[KnowledgeQuestion]:
        """상위 관련성 질문 조회"""
        query = select(KnowledgeQuestion).where(
            KnowledgeQuestion.user_id == user_id,
            KnowledgeQuestion.status == QuestionStatus.NEW
        ).order_by(
            desc(KnowledgeQuestion.relevance_score),
            desc(KnowledgeQuestion.reward_points)
        ).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())
