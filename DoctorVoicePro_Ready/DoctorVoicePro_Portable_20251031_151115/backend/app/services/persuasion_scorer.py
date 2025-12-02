"""
Persuasion Score Calculator
설득력 점수 계산 모듈
"""

import re
from typing import Dict


class PersuasionScorer:
    """
    블로그 글의 설득력 점수를 계산
    """

    # 감정 키워드
    EMOTIONAL_WORDS = [
        "고민",
        "걱정",
        "불안",
        "두려움",
        "아픔",
        "고통",
        "괴로움",
        "희망",
        "안심",
        "행복",
        "기쁨",
        "회복",
        "건강",
    ]

    # 권위 신호
    AUTHORITY_SIGNALS = [
        r"\d+년\s*(?:간|동안|경력)",
        r"\d+(?:명|분).*?(?:환자|치료)",
        r"(?:연구|논문|임상)",
        r"(?:전문의|교수|박사)",
        r"(?:대한|학회|협회)",
    ]

    # 데이터/통계 패턴
    DATA_PATTERNS = [
        r"\d+%",
        r"\d+명\s*중\s*\d+명",
        r"\d+배",
        r"\d+건",
        r"(?:통계|연구|조사).*?\d+",
    ]

    # CTA (Call To Action) 패턴
    CTA_PATTERNS = [
        r"(?:예약|상담|문의).*?(?:주세요|하세요|바랍니다)",
        r"(?:지금|오늘|당장)\s*(?:예약|상담)",
        r"(?:연락|전화).*?(?:주시면|드리면)",
        r"(?:무료|부담없이)\s*(?:상담|검사)",
    ]

    def calculate_score(self, text: str) -> Dict[str, float]:
        """
        전체 설득력 점수 계산

        Returns:
            {
                "storytelling": 0-100,
                "data_evidence": 0-100,
                "emotion": 0-100,
                "authority": 0-100,
                "social_proof": 0-100,
                "cta_clarity": 0-100,
                "total": 0-100
            }
        """
        scores = {
            "storytelling": self._check_storytelling(text),
            "data_evidence": self._check_data_evidence(text),
            "emotion": self._check_emotional_appeal(text),
            "authority": self._check_authority(text),
            "social_proof": self._check_social_proof(text),
            "cta_clarity": self._check_cta(text),
        }

        # 전체 점수는 가중 평균
        weights = {
            "storytelling": 0.20,
            "data_evidence": 0.20,
            "emotion": 0.15,
            "authority": 0.20,
            "social_proof": 0.10,
            "cta_clarity": 0.15,
        }

        total = sum(scores[key] * weights[key] for key in scores)
        scores["total"] = round(total, 1)

        return scores

    def _check_storytelling(self, text: str) -> float:
        """
        스토리텔링 요소 검사
        """
        score = 0

        # 1. 도입부에 질문이나 공감 표현 (20점)
        first_paragraph = text[:200]
        if re.search(r"[?？]", first_paragraph):
            score += 10
        if any(
            word in first_paragraph
            for word in ["혹시", "만약", "이런", "저런", "여러분"]
        ):
            score += 10

        # 2. 사례/이야기 언급 (30점)
        story_patterns = [
            r"환자분?[이가]",
            r"(?:얼마\s*전|최근|지난주)\s*.*?분",
            r"\d+대\s*(?:남성|여성|환자)",
            r"사례",
            r"경우",
        ]
        story_count = sum(
            len(re.findall(pattern, text)) for pattern in story_patterns
        )
        score += min(30, story_count * 10)

        # 3. 시간의 흐름 (20점)
        time_markers = ["처음", "그때", "그후", "이후", "지금", "현재", "결국"]
        time_count = sum(1 for marker in time_markers if marker in text)
        score += min(20, time_count * 5)

        # 4. 대화체/인용 (30점)
        if re.search(r"[\"\"''].*?[\"\"'']", text):
            score += 15
        if any(word in text for word in ["말씀", "이야기", "물어", "답변"]):
            score += 15

        return min(100, score)

    def _check_data_evidence(self, text: str) -> float:
        """
        데이터/근거 활용도 검사
        """
        score = 0

        # 통계 및 숫자 데이터
        data_count = 0
        for pattern in self.DATA_PATTERNS:
            data_count += len(re.findall(pattern, text))

        score += min(60, data_count * 20)

        # 연구/논문 인용
        if re.search(r"(?:연구|논문|조사|임상)", text):
            score += 20

        # 구체적인 수치
        number_matches = re.findall(r"\d+", text)
        if len(number_matches) >= 3:
            score += 20

        return min(100, score)

    def _check_emotional_appeal(self, text: str) -> float:
        """
        감정 공감 요소 검사
        """
        score = 0

        # 감정 키워드 개수
        emotion_count = sum(1 for word in self.EMOTIONAL_WORDS if word in text)
        score += min(50, emotion_count * 10)

        # 공감 표현
        empathy_words = ["이해", "공감", "느끼", "마음", "심정"]
        empathy_count = sum(1 for word in empathy_words if word in text)
        score += min(30, empathy_count * 10)

        # 2인칭 호칭 (독자와의 거리 좁히기)
        if re.search(r"(?:여러분|당신|귀하)", text):
            score += 20

        return min(100, score)

    def _check_authority(self, text: str) -> float:
        """
        권위/전문성 신호 검사
        """
        score = 0

        # 권위 신호 개수
        authority_count = 0
        for pattern in self.AUTHORITY_SIGNALS:
            authority_count += len(re.findall(pattern, text))

        score += min(70, authority_count * 25)

        # 전문 용어 적절히 사용 (너무 많으면 감점)
        medical_terms = re.findall(r"[가-힣]{2,}(?:염|증|병|질환|치료|수술)", text)
        term_count = len(medical_terms)

        if 3 <= term_count <= 8:  # 적정 수준
            score += 30
        elif term_count > 8:  # 너무 많음
            score += 10

        return min(100, score)

    def _check_social_proof(self, text: str) -> float:
        """
        사회적 증거 검사
        """
        score = 0

        # 환자 후기/사례
        if re.search(r"(?:후기|사례|경험)", text):
            score += 30

        # 숫자로 된 사회적 증거
        social_numbers = re.findall(
            r"\d+(?:명|분|건|례|년|개월).*?(?:환자|치료|시술|수술|상담)", text
        )
        score += min(40, len(social_numbers) * 20)

        # 일반화 표현
        general_phrases = ["많은", "대부분", "흔히", "일반적"]
        score += min(30, sum(1 for phrase in general_phrases if phrase in text) * 10)

        return min(100, score)

    def _check_cta(self, text: str) -> float:
        """
        행동 유도 명확성 검사
        """
        score = 0

        # CTA 패턴 존재 여부
        cta_count = 0
        for pattern in self.CTA_PATTERNS:
            cta_count += len(re.findall(pattern, text))

        if cta_count >= 1:
            score += 50

        # 글 후반부에 CTA 있는지 (더 효과적)
        last_part = text[-300:]
        if any(re.search(pattern, last_part) for pattern in self.CTA_PATTERNS):
            score += 30

        # 연락처/예약 관련 언급
        contact_words = ["전화", "연락", "예약", "방문", "내원"]
        if any(word in text for word in contact_words):
            score += 20

        return min(100, score)

    def get_recommendations(self, scores: Dict[str, float]) -> list:
        """
        점수 기반 개선 제안

        Args:
            scores: calculate_score()의 결과

        Returns:
            개선 제안 리스트
        """
        recommendations = []

        if scores["storytelling"] < 60:
            recommendations.append(
                "스토리텔링 강화: 실제 환자 사례나 경험담을 추가하면 공감도가 높아집니다."
            )

        if scores["data_evidence"] < 60:
            recommendations.append(
                "데이터 보강: 통계나 연구 결과를 1-2개 더 추가하면 신뢰도가 높아집니다."
            )

        if scores["emotion"] < 60:
            recommendations.append(
                "감정 공감: 환자의 고민이나 걱정을 더 구체적으로 언급하세요."
            )

        if scores["authority"] < 60:
            recommendations.append(
                "전문성 강화: 경력이나 치료 건수 등 권위 신호를 추가하세요."
            )

        if scores["social_proof"] < 60:
            recommendations.append(
                "사회적 증거: '많은 환자분들이', '대부분의 경우' 같은 표현을 활용하세요."
            )

        if scores["cta_clarity"] < 60:
            recommendations.append(
                "행동 유도 명확화: 글 마지막에 예약이나 상담을 권유하는 문장을 추가하세요."
            )

        return recommendations


# Singleton instance
persuasion_scorer = PersuasionScorer()
