"""
SEO Optimizer
네이버 블로그 SEO 최적화 모듈
"""

import re
from typing import List, Dict, Set
from collections import Counter


class SEOOptimizer:
    """
    네이버 블로그 검색 최적화
    """

    # 환자 검색 의도 키워드
    SEARCH_INTENTS = [
        "증상",
        "원인",
        "치료",
        "방법",
        "병원",
        "비용",
        "후기",
        "추천",
        "예방",
        "효과",
        "부작용",
        "검사",
        "진단",
        "수술",
        "자가진단",
        "자연치유",
    ]

    # 의학 관련 접미사
    MEDICAL_SUFFIXES = ["염", "증", "병", "질환", "장애", "통증", "암"]

    # 제목에서 제외할 불필요한 패턴
    EXCLUDE_PATTERNS = [
        r"효과\s*없다면",
        r"계속\s*재발\s*한다면",
        r"재발\s*한다면",
        r"대신",
        r"['\"]\w+['\"]",  # 따옴표로 감싼 단어
        r"O{2,}",  # OOO, OO 같은 패턴
        r"이렇게",
        r"그렇게",
        r"무슨\s*원리일까\??",
        r"어떻게",
        r"어렵지\s*않습니다?",
        r"어렵지않습니다?",
        r"하면",
        r"부터\s*확인하세요",
        r"강화하세요",
        r"확인하세요",
    ]

    def extract_keyword_from_title(self, title: str) -> str:
        """
        제목에서 주요 키워드 추출 (띄어쓰기 제거)

        예시:
        - "만성 두드러기 병원 효과 없다면 OOO부터 확인하세요" -> "만성두드러기병원"
        - "항문 주변 따가움 '이렇게' 하면 치료 어렵지않습니다" -> "항문주변따가움"
        - "서울 아토피 피부과 대신 혈액치료, 무슨 원리일까?" -> "서울아토피피부과"

        Args:
            title: 블로그 제목

        Returns:
            띄어쓰기가 제거된 키워드
        """
        # 제외할 단어 리스트 (더 간단하고 직접적인 방식)
        exclude_words = [
            "효과", "없다면", "계속", "재발", "재발한다면", "한다면",
            "대신", "이렇게", "그렇게", "어떻게", "어렵지", "않습니다",
            "어렵지않습니다", "하면", "부터", "확인하세요", "확인",
            "강화하세요", "강화", "무슨", "원리", "원리일까", "치료",
            "혈액치료", "혈액", "방법",
        ]

        # 특수문자 및 구두점 제거
        processed_title = re.sub(r"[,?!.…、。]", " ", title)

        # 따옴표로 감싼 단어 제거
        processed_title = re.sub(r"['\"][\w가-힣]+['\"]", " ", processed_title)

        # OOO, OO 같은 패턴 제거
        processed_title = re.sub(r"\bO{2,}\b", " ", processed_title)

        # 여러 공백을 하나로
        processed_title = re.sub(r"\s+", " ", processed_title).strip()

        # 단어 분리
        words = processed_title.split()

        # 의미있는 의료 키워드만 추출
        keyword_words = []
        for word in words:
            # 한글 2글자 이상
            if not re.match(r"^[가-힣]{2,}$", word):
                continue

            # 제외 단어가 아닌 경우만 포함
            if word not in exclude_words:
                keyword_words.append(word)

                # 3-4개 단어까지만 (의료 키워드는 보통 이 정도 길이)
                if len(keyword_words) >= 4:
                    break

        # 총 길이가 너무 길면 3개까지만 (예: 각 단어가 4글자면 12글자)
        total_length = sum(len(w) for w in keyword_words)
        if total_length > 12 and len(keyword_words) > 3:
            keyword_words = keyword_words[:3]

        # 띄어쓰기 제거하고 하나로 합치기
        keyword = "".join(keyword_words)

        # 키워드가 너무 짧으면 원본 제목의 첫 단어 사용
        if len(keyword) < 4:
            first_words = [w for w in title.split()[:3] if re.match(r"^[가-힣]{2,}$", w)]
            keyword = "".join(first_words[:3])

        return keyword if keyword else title.split()[0] if title else "키워드"

    def extract_keywords(
        self, content: str, specialty: str, location: str = ""
    ) -> List[str]:
        """
        콘텐츠에서 SEO 키워드 추출

        Args:
            content: 블로그 콘텐츠
            specialty: 진료 과목
            location: 병원 위치

        Returns:
            검색 최적화된 키워드 리스트
        """
        # 1. 의학 용어 추출
        medical_terms = self._extract_medical_terms(content)

        # 2. 키워드 조합 생성
        keywords = set()

        # 의학 용어 + 검색 의도
        for term in medical_terms[:5]:  # 상위 5개 용어만
            for intent in self.SEARCH_INTENTS[:10]:
                keywords.add(f"{term} {intent}")

        # 지역 키워드 조합
        if location:
            for term in medical_terms[:3]:
                keywords.add(f"{location} {term}")
                keywords.add(f"{location} {term} 치료")
                keywords.add(f"{location} {term} 병원")

        # 진료과 조합
        if specialty:
            keywords.add(f"{specialty} 추천")
            keywords.add(f"{location} {specialty}" if location else f"{specialty}")

        # 리스트로 변환하고 길이 제한
        keyword_list = list(keywords)[:20]

        return keyword_list

    def _extract_medical_terms(self, text: str) -> List[str]:
        """
        텍스트에서 의학 용어 추출
        """
        # 의학 용어 패턴 (한글 2-6자 + 특정 접미사)
        terms = []

        for suffix in self.MEDICAL_SUFFIXES:
            pattern = rf"([가-힣]{{2,6}}{suffix})"
            matches = re.findall(pattern, text)
            terms.extend(matches)

        # 빈도수 기반 정렬
        term_counts = Counter(terms)
        sorted_terms = [term for term, count in term_counts.most_common(10)]

        return sorted_terms

    def generate_hashtags(
        self, content: str, medical_terms: List[str], specialty: str, location: str = ""
    ) -> List[str]:
        """
        해시태그 생성

        Args:
            content: 콘텐츠
            medical_terms: 의학 용어 리스트
            specialty: 진료 과목
            location: 위치

        Returns:
            해시태그 리스트 (# 포함)
        """
        hashtags = []

        # 1. 의학 용어 해시태그
        for term in medical_terms[:5]:
            hashtags.append(f"#{term}")
            hashtags.append(f"#{term}치료")

        # 2. 진료과 해시태그
        if specialty:
            hashtags.append(f"#{specialty}")
            hashtags.append(f"#{specialty}추천")

        # 3. 지역 해시태그
        if location:
            hashtags.append(f"#{location}{specialty}" if specialty else f"#{location}")
            if medical_terms:
                hashtags.append(f"#{location}{medical_terms[0]}")

        # 4. 일반 건강 해시태그
        general_tags = ["#건강", "#건강정보", "#의학정보"]
        hashtags.extend(general_tags)

        # 중복 제거 및 개수 제한
        unique_hashtags = list(dict.fromkeys(hashtags))[:15]

        return unique_hashtags

    def generate_meta_description(self, content: str, title: str = "") -> str:
        """
        메타 설명 생성 (150-160자)

        Args:
            content: 콘텐츠
            title: 제목

        Returns:
            메타 설명
        """
        # 첫 2-3 문장 추출
        sentences = re.split(r"[.!?]\s+", content[:500])

        # 제목이 있으면 포함
        if title:
            meta = f"{title}. "
        else:
            meta = ""

        # 문장 추가
        for sentence in sentences[:3]:
            if len(meta) + len(sentence) < 150:
                meta += sentence + ". "
            else:
                break

        # 길이 조정
        if len(meta) > 160:
            meta = meta[:157] + "..."

        return meta.strip()

    def generate_subheadings(self, content: str) -> List[str]:
        """
        콘텐츠 구조 분석하여 소제목 추출/생성

        Args:
            content: 콘텐츠

        Returns:
            소제목 리스트
        """
        subheadings = []

        # 기존 소제목 찾기 (━━━ 로 구분되거나 번호 매겨진 것)
        heading_patterns = [
            r"━+\s*\n(.+?)\n\s*━+",  # ━━ 제목 ━━
            r"^\d+\.\s*(.+)$",  # 1. 제목
            r"^[■□●○▶▷]\s*(.+)$",  # ■ 제목
        ]

        lines = content.split("\n")
        for line in lines:
            for pattern in heading_patterns:
                match = re.match(pattern, line.strip())
                if match:
                    subheadings.append(match.group(1).strip())

        # 소제목이 없으면 자동 생성 제안
        if not subheadings:
            # 일반적인 의료 블로그 구조
            medical_terms = self._extract_medical_terms(content)
            if medical_terms:
                term = medical_terms[0]
                subheadings = [
                    f"{term}이란?",
                    f"{term}의 주요 증상",
                    f"{term} 원인",
                    "치료 방법",
                    "예방 및 관리",
                    "자주 묻는 질문",
                ]

        return subheadings[:6]  # 최대 6개

    def analyze_readability(self, content: str) -> Dict:
        """
        가독성 분석

        Returns:
            {
                "avg_sentence_length": 평균 문장 길이,
                "paragraph_count": 문단 수,
                "readability_score": 가독성 점수 (0-100)
            }
        """
        # 문장 분리
        sentences = re.split(r"[.!?]\s+", content)
        sentences = [s.strip() for s in sentences if s.strip()]

        # 평균 문장 길이
        avg_length = sum(len(s) for s in sentences) / len(sentences) if sentences else 0

        # 문단 수
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        paragraph_count = len(paragraphs)

        # 가독성 점수 계산
        readability = 100

        # 문장이 너무 길면 감점
        if avg_length > 80:
            readability -= (avg_length - 80) * 0.5

        # 문단이 너무 적으면 감점
        if paragraph_count < 3:
            readability -= 20

        # 문장이 너무 짧아도 감점 (단조로움)
        if avg_length < 20:
            readability -= 10

        readability = max(0, min(100, readability))

        return {
            "avg_sentence_length": round(avg_length, 1),
            "paragraph_count": paragraph_count,
            "readability_score": round(readability, 1),
        }

    def get_seo_score(
        self, content: str, title: str, keywords: List[str], hashtags: List[str]
    ) -> float:
        """
        전체 SEO 점수 계산 (0-100)

        Args:
            content: 콘텐츠
            title: 제목
            keywords: 키워드 리스트
            hashtags: 해시태그 리스트

        Returns:
            SEO 점수
        """
        score = 0

        # 1. 제목 최적화 (30점)
        if title:
            if 30 <= len(title) <= 60:  # 적절한 길이
                score += 15
            if any(keyword.split()[0] in title for keyword in keywords[:3]):  # 키워드 포함
                score += 15

        # 2. 키워드 밀도 (20점)
        if keywords:
            keyword_density = sum(
                content.lower().count(keyword.lower()) for keyword in keywords[:5]
            )
            score += min(20, keyword_density * 2)

        # 3. 콘텐츠 길이 (15점)
        content_length = len(content)
        if 1000 <= content_length <= 3000:  # 적정 길이
            score += 15
        elif content_length > 500:
            score += 10

        # 4. 해시태그 (15점)
        if 5 <= len(hashtags) <= 15:
            score += 15

        # 5. 구조화 (소제목) (10점)
        subheadings = self.generate_subheadings(content)
        if subheadings:
            score += 10

        # 6. 가독성 (10점)
        readability = self.analyze_readability(content)
        if readability["readability_score"] >= 70:
            score += 10

        return min(100, score)


# Singleton instance
seo_optimizer = SEOOptimizer()
