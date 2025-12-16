"""
Post Service
포스팅 생성 및 관리 서비스 - 모든 모듈 통합
"""

from typing import Dict, Optional
from uuid import UUID
import uuid as uuid_pkg
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import User, DoctorProfile, Post, PostVersion, AIUsage, calculate_cost
from app.models.top_post_analysis import AggregatedPattern
from app.services.ai_rewrite_engine import ai_rewrite_engine
from app.services.medical_law_checker import medical_law_checker
from app.services.persuasion_scorer import persuasion_scorer
from app.services.seo_optimizer import seo_optimizer
from app.services.forbidden_words_checker import forbidden_words_checker
from app.services.content_analyzer import content_analyzer
from app.services.dia_crank_analyzer import dia_crank_analyzer
from app.services.top_post_analyzer import detect_category, CATEGORIES


class PostService:
    """
    포스팅 생성 및 관리를 담당하는 통합 서비스
    """

    async def create_post(
        self,
        db: AsyncSession,
        user_id: UUID,
        original_content: str,
        persuasion_level: int = 3,
        framework: str = "AIDA",
        target_length: int = 1500,
        writing_style: Optional[Dict] = None,
        requirements: Optional[Dict] = None,
        ai_provider: str = "gpt",
        ai_model: Optional[str] = None,
        seo_optimization: Optional[Dict] = None,
        top_post_rules: Optional[Dict] = None,
        websocket_manager=None,
        task_id: str = None,
    ) -> Post:
        """
        새로운 포스팅 생성 (전체 파이프라인 실행)

        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            original_content: 원본 의료 정보
            persuasion_level: 각색 레벨 (1-5)
            framework: 설득 프레임워크
            target_length: 목표 길이
            writing_style: 사용자 지정 말투 설정
            requirements: 특별 요청사항 (common/individual)
            ai_provider: AI 제공자 ("claude" 또는 "gpt")
            ai_model: 사용할 모델
            seo_optimization: SEO 최적화 설정 (DIA/CRANK)
            websocket_manager: WebSocket 관리자 (선택)
            task_id: 작업 ID (WebSocket 사용 시 필수)

        Returns:
            생성된 Post 객체
        """
        # Generate task_id if not provided
        if not task_id:
            task_id = str(uuid_pkg.uuid4())

        # Helper function to send progress
        async def send_progress(stage: str, progress: int, message: str, data: dict = None):
            if websocket_manager:
                try:
                    await websocket_manager.send_progress(
                        str(user_id), task_id, stage, progress, message, data
                    )
                except Exception as e:
                    # Don't fail the entire operation if WebSocket fails
                    print(f"WebSocket error: {e}")

        await send_progress("init", 0, "작업을 시작합니다...", {})

        # 1. 사용자 및 프로필 로드 (로그인 불필요)
        await send_progress("profile", 10, "프로필을 불러옵니다...", {})

        if user_id:
            # 로그인한 경우
            user = await self._get_user_optional(db, user_id)
            profile = await self._get_doctor_profile(db, user_id) if user else None
        else:
            # 로그인하지 않은 경우 - 기본 프로필 사용
            user = None
            profile = None

        if not profile:
            # 프로필이 없으면 기본 프로필 생성
            profile = self._create_anonymous_profile()

        # 프로필을 딕셔너리로 변환
        profile_dict = self._profile_to_dict(user, profile)

        # 1.5. 상위노출 규칙 자동 적용 (top_post_rules가 없을 경우)
        if not top_post_rules:
            top_post_rules = await self._get_auto_rules(db, original_content)
            if top_post_rules:
                await send_progress("rules", 15, "상위노출 규칙을 자동 적용합니다...", {
                    "category": top_post_rules.get("category_name", "일반")
                })

        # 2. AI 각색 실행
        await send_progress("rewriting", 20, "AI가 콘텐츠를 각색하고 있습니다...", {})

        # target_audience 가져오기
        if isinstance(profile, dict):
            target_audience = profile.get("target_audience")
        elif profile:
            target_audience = profile.target_audience
        else:
            target_audience = None

        generated_content = await ai_rewrite_engine.generate(
            original_content=original_content,
            doctor_profile=profile_dict,
            framework=framework,
            persuasion_level=persuasion_level,
            target_length=target_length,
            target_audience=target_audience,
            custom_writing_style=writing_style,
            requirements=requirements,
            ai_provider=ai_provider,
            ai_model=ai_model,
            seo_optimization=seo_optimization,
            top_post_rules=top_post_rules,
        )

        # AI 사용량 기록
        usage_info = None
        if hasattr(ai_rewrite_engine, 'last_usage') and ai_rewrite_engine.last_usage:
            usage = ai_rewrite_engine.last_usage
            cost = calculate_cost(
                usage.get("ai_model", ""),
                usage.get("input_tokens", 0),
                usage.get("output_tokens", 0)
            )

            usage_info = {
                **usage,
                **cost,
            }

            # DB에 사용량 저장
            try:
                ai_usage = AIUsage(
                    user_id=user_id,
                    ai_provider=usage.get("ai_provider", ai_provider),
                    ai_model=usage.get("ai_model", ai_model or "unknown"),
                    input_tokens=usage.get("input_tokens", 0),
                    output_tokens=usage.get("output_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                    cost_usd=cost.get("total_cost_usd", 0),
                    cost_krw=cost.get("total_cost_krw", 0),
                    request_type="content_generation",
                    content_length=len(generated_content),
                )
                db.add(ai_usage)
                await db.flush()  # 즉시 저장
            except Exception as e:
                print(f"AI 사용량 기록 실패: {e}")

        # 3. 의료법 검증
        await send_progress("law_check", 50, "의료법 준수 여부를 검증하고 있습니다...", {})
        law_check = medical_law_checker.check(generated_content)

        # 위반 사항이 있으면 자동 수정
        if not law_check["is_compliant"]:
            await send_progress("law_fix", 55, "의료법 위반 사항을 자동 수정하고 있습니다...", {})
            generated_content, changes = medical_law_checker.auto_fix(
                generated_content
            )
            # 재검증
            law_check = medical_law_checker.check(generated_content)
            law_check["auto_fixed"] = True
            law_check["changes"] = changes

        # 4. 설득력 점수 계산
        await send_progress("scoring", 70, "설득력 점수를 계산하고 있습니다...", {})
        persuasion_scores = persuasion_scorer.calculate_score(generated_content)

        # 5. SEO 최적화
        await send_progress("seo", 80, "SEO 최적화를 진행하고 있습니다...", {})
        medical_terms = seo_optimizer._extract_medical_terms(generated_content)

        # user가 None이어도 작동하도록
        hospital_name = user.hospital_name if user else ""
        specialty = user.specialty if user else "의료"
        location = self._extract_location(hospital_name)

        seo_keywords = seo_optimizer.extract_keywords(
            generated_content, specialty, location
        )

        hashtags = seo_optimizer.generate_hashtags(
            generated_content, medical_terms, specialty, location
        )

        # 6. 제목 및 메타 설명 생성
        await send_progress("title", 80, "제목과 메타 설명을 생성하고 있습니다...", {})
        title_meta = await ai_rewrite_engine.generate_title_and_meta(
            generated_content, specialty
        )

        title = title_meta.get("title", "")
        meta_description = title_meta.get("meta_description", "")
        ai_hashtags = title_meta.get("hashtags", [])

        # 7. 금칙어 검사 및 자동 대체
        await send_progress("forbidden", 85, "금칙어를 검사하고 있습니다...", {})
        generated_content, forbidden_replacements = forbidden_words_checker.check_and_replace(generated_content)

        # 제목도 금칙어 검사
        title, title_replacements = forbidden_words_checker.check_and_replace(title)

        forbidden_check_result = {
            "content_replacements": forbidden_replacements,
            "title_replacements": title_replacements,
        }

        # 8. 콘텐츠 분석 (글자수, 키워드)
        await send_progress("analyzing", 88, "콘텐츠를 분석하고 있습니다...", {})
        content_analysis = content_analyzer.analyze(generated_content)

        # 9. 후킹성 제목 5개 생성
        await send_progress("titles", 91, "추천 제목을 생성하고 있습니다...", {})
        suggested_titles = await ai_rewrite_engine.generate_hooking_titles(generated_content, specialty)

        # 10. 소제목 4개 생성
        await send_progress("subtitles", 94, "추천 소제목을 생성하고 있습니다...", {})
        suggested_subtitles = await ai_rewrite_engine.generate_subtitles(generated_content)

        # 11. DIA/CRANK 분석
        await send_progress("dia_crank", 96, "DIA/CRANK 점수를 분석하고 있습니다...", {})
        dia_crank_analysis = await dia_crank_analyzer.analyze(generated_content, title)

        # 제목에서 메인 키워드 추출 (띄어쓰기 제거)
        main_keyword = seo_optimizer.extract_keyword_from_title(title)

        # 메인 키워드를 SEO 키워드 리스트 맨 앞에 추가
        if main_keyword and main_keyword not in seo_keywords:
            seo_keywords = [main_keyword] + seo_keywords

        # 해시태그 병합 (중복 제거)
        all_hashtags = list(set(hashtags + [f"#{tag}" for tag in ai_hashtags]))[:15]

        # 12. DB에 저장
        await send_progress("saving", 98, "포스팅을 저장하고 있습니다...", {})
        post = Post(
            user_id=user_id,
            title=title,
            original_content=original_content,
            generated_content=generated_content,
            persuasion_score=persuasion_scores["total"],
            medical_law_check=law_check,
            seo_keywords=seo_keywords,
            hashtags=all_hashtags,
            meta_description=meta_description,
            status="draft",
            # 새로운 필드들
            suggested_titles=suggested_titles,
            suggested_subtitles=suggested_subtitles,
            content_analysis=content_analysis,
            forbidden_words_check=forbidden_check_result,
            dia_crank_analysis=dia_crank_analysis,
        )

        db.add(post)
        await db.commit()
        await db.refresh(post)

        # 8. 첫 번째 버전 저장
        version = PostVersion(
            post_id=post.id,
            version_number=1,
            content=generated_content,
            persuasion_score=persuasion_scores["total"],
            generation_config={
                "framework": framework,
                "persuasion_level": persuasion_level,
                "target_length": target_length,
            },
        )

        db.add(version)
        await db.commit()

        # 완료 메시지 전송
        await send_progress("completed", 100, "포스팅 생성이 완료되었습니다!", {
            "post_id": str(post.id),
            "title": title,
            "persuasion_score": persuasion_scores["total"]
        })

        if websocket_manager:
            try:
                await websocket_manager.send_completion(
                    str(user_id),
                    task_id,
                    True,
                    "포스팅이 성공적으로 생성되었습니다.",
                    {"post_id": str(post.id)}
                )
            except Exception as e:
                print(f"WebSocket error: {e}")

        return post

    async def rewrite_post(
        self,
        db: AsyncSession,
        post_id: UUID,
        user_id: UUID,
        persuasion_level: Optional[int] = None,
        framework: Optional[str] = None,
        target_length: Optional[int] = None,
    ) -> Post:
        """
        기존 포스팅 재작성

        Args:
            db: 데이터베이스 세션
            post_id: 포스트 ID
            user_id: 사용자 ID
            persuasion_level: 새로운 각색 레벨
            framework: 새로운 프레임워크
            target_length: 새로운 목표 길이

        Returns:
            업데이트된 Post 객체
        """
        # 기존 포스트 로드
        result = await db.execute(
            select(Post).where(Post.id == post_id, Post.user_id == user_id)
        )
        post = result.scalar_one_or_none()

        if not post:
            raise ValueError("포스트를 찾을 수 없습니다")

        # 사용자 및 프로필 로드
        user = await self._get_user(db, user_id)
        profile = await self._get_doctor_profile(db, user_id)
        profile_dict = self._profile_to_dict(user, profile)

        # 기존 설정 또는 새 설정 사용
        framework = framework or "AIDA"
        persuasion_level = persuasion_level or 3
        target_length = target_length or 1500

        # AI 재작성
        generated_content = await ai_rewrite_engine.generate(
            original_content=post.original_content,
            doctor_profile=profile_dict,
            framework=framework,
            persuasion_level=persuasion_level,
            target_length=target_length,
            target_audience=profile.target_audience if profile else None,
        )

        # 검증 및 점수 계산
        law_check = medical_law_checker.check(generated_content)
        if not law_check["is_compliant"]:
            generated_content, _ = medical_law_checker.auto_fix(generated_content)
            law_check = medical_law_checker.check(generated_content)

        persuasion_scores = persuasion_scorer.calculate_score(generated_content)

        # 버전 번호 계산
        version_count_result = await db.execute(
            select(PostVersion).where(PostVersion.post_id == post_id)
        )
        version_count = len(version_count_result.scalars().all())
        new_version_number = version_count + 1

        # 새 버전 저장
        version = PostVersion(
            post_id=post.id,
            version_number=new_version_number,
            content=generated_content,
            persuasion_score=persuasion_scores["total"],
            generation_config={
                "framework": framework,
                "persuasion_level": persuasion_level,
                "target_length": target_length,
            },
        )

        db.add(version)

        # 포스트 업데이트
        post.generated_content = generated_content
        post.persuasion_score = persuasion_scores["total"]
        post.medical_law_check = law_check

        await db.commit()
        await db.refresh(post)

        return post

    async def _get_user(self, db: AsyncSession, user_id: UUID) -> User:
        """사용자 조회"""
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("사용자를 찾을 수 없습니다")
        return user

    async def _get_user_optional(self, db: AsyncSession, user_id: UUID) -> Optional[User]:
        """사용자 조회 (Optional)"""
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def _get_doctor_profile(
        self, db: AsyncSession, user_id: UUID
    ) -> Optional[DoctorProfile]:
        """의사 프로필 조회"""
        result = await db.execute(
            select(DoctorProfile).where(DoctorProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def _create_default_profile(
        self, db: AsyncSession, user: User
    ) -> DoctorProfile:
        """기본 프로필 생성"""
        profile = DoctorProfile(
            user_id=user.id,
            writing_style={
                "formality": 5,
                "friendliness": 7,
                "technical_depth": 5,
                "storytelling": 6,
                "emotion": 6,
            },
            signature_phrases=None,
            sample_posts=None,
            target_audience=None,
            preferred_structure="AIDA",
        )

        db.add(profile)
        await db.commit()
        await db.refresh(profile)

        return profile

    def _create_anonymous_profile(self) -> dict:
        """익명 사용자용 기본 프로필 생성 (DB 저장 없음)"""
        return {
            "writing_style": {
                "formality": 5,
                "friendliness": 7,
                "technical_depth": 5,
                "storytelling": 6,
                "emotion": 6,
            },
            "signature_phrases": [],
            "target_audience": {},
            "preferred_structure": "AIDA",
        }

    def _profile_to_dict(self, user: Optional[User], profile: Optional[DoctorProfile]) -> Dict:
        """프로필을 딕셔너리로 변환 (user가 None이어도 가능)"""
        # 익명 사용자 또는 프로필 없음
        if not profile and not user:
            return {
                "name": "원장님",
                "specialty": "의료",
                "writing_style": {
                    "formality": 5,
                    "friendliness": 7,
                    "technical_depth": 5,
                    "storytelling": 6,
                    "emotion": 6,
                },
                "signature_phrases": [],
                "target_audience": {},
            }

        # 프로필이 dict인 경우 (익명 프로필)
        if isinstance(profile, dict):
            return {
                "name": user.name if user else "원장님",
                "specialty": user.specialty if user else "의료",
                "writing_style": profile.get("writing_style", {}),
                "signature_phrases": profile.get("signature_phrases", []),
                "target_audience": profile.get("target_audience", {}),
            }

        # 일반 프로필
        if not profile:
            return {
                "name": user.name if user else "원장님",
                "specialty": user.specialty if user else "의료",
                "writing_style": {
                    "formality": 5,
                    "friendliness": 7,
                    "technical_depth": 5,
                    "storytelling": 6,
                    "emotion": 6,
                },
                "signature_phrases": [],
                "target_audience": {},
            }

        return {
            "name": user.name if user else "원장님",
            "specialty": user.specialty if user else "의료",
            "writing_style": profile.writing_style or {},
            "signature_phrases": profile.signature_phrases or [],
            "target_audience": profile.target_audience or {},
        }

    def _extract_location(self, hospital_name: str) -> str:
        """병원명에서 지역 추출"""
        # 간단한 지역 추출 (예: "서울 강남구", "부산" 등)
        locations = [
            "서울",
            "강남",
            "강북",
            "송파",
            "강서",
            "부산",
            "대구",
            "인천",
            "광주",
            "대전",
            "울산",
            "세종",
        ]

        for loc in locations:
            if loc in hospital_name:
                return loc

        return ""

    async def _get_auto_rules(self, db: AsyncSession, content: str) -> Optional[Dict]:
        """
        콘텐츠 기반으로 카테고리를 감지하고 해당 카테고리의 규칙을 자동으로 가져옴

        Args:
            db: 데이터베이스 세션
            content: 원본 콘텐츠

        Returns:
            규칙 딕셔너리 또는 None
        """
        try:
            # 콘텐츠에서 카테고리 감지
            category = detect_category(content)

            # 해당 카테고리의 패턴 조회
            result = await db.execute(
                select(AggregatedPattern).where(AggregatedPattern.category == category)
            )
            pattern = result.scalar_one_or_none()

            # 데이터가 충분하지 않으면 None 반환
            if not pattern or pattern.sample_count < 3:
                return None

            # 최적 키워드 위치 결정
            positions = {
                "front": pattern.keyword_position_front,
                "middle": pattern.keyword_position_middle,
                "end": pattern.keyword_position_end
            }
            best_position = max(positions, key=positions.get)

            # 규칙 생성
            rules = {
                "category": category,
                "category_name": CATEGORIES.get(category, {}).get("name", "일반"),
                "sample_count": pattern.sample_count,
                "confidence": min(1.0, pattern.sample_count / 30),
                "title": {
                    "length": {
                        "optimal": round(pattern.avg_title_length),
                        "min": max(15, round(pattern.avg_title_length * 0.7)),
                        "max": min(60, round(pattern.avg_title_length * 1.3))
                    },
                    "keyword_placement": {
                        "include_keyword": pattern.title_keyword_rate > 0.5,
                        "best_position": best_position
                    }
                },
                "content": {
                    "length": {
                        "optimal": round(pattern.avg_content_length),
                        "min": max(500, round(pattern.avg_content_length * 0.7)),
                        "max": round(pattern.avg_content_length * 1.3)
                    },
                    "structure": {
                        "heading_count": round(pattern.avg_heading_count),
                        "keyword_density": round(pattern.avg_keyword_density, 2),
                        "keyword_count": round(pattern.avg_keyword_count)
                    }
                },
                "media": {
                    "images": {
                        "optimal": round(pattern.avg_image_count),
                        "min": max(3, pattern.min_image_count),
                        "max": pattern.max_image_count
                    }
                }
            }

            print(f"[자동규칙] 카테고리 '{category}' 규칙 적용 (샘플 {pattern.sample_count}개)")
            return rules

        except Exception as e:
            print(f"[자동규칙] 규칙 조회 실패: {e}")
            return None


# Singleton instance
post_service = PostService()
