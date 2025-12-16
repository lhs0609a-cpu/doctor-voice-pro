"""
콘텐츠 분석 서비스 - 글자수, 키워드 분석
"""

import re
from typing import Dict, List
from collections import Counter


class ContentAnalyzer:
    """콘텐츠 분석기 - 글자수, 키워드 분석"""

    # 의미 없는 단어들 (불용어)
    STOP_WORDS = {
        '은', '는', '이', '가', '을', '를', '의', '에', '와', '과', '도', '로', '으로',
        '게', '께', '에게', '한테', '더', '가장', '매우', '너무', '아주', '정말', '진짜',
        '것', '수', '등', '및', '또는', '그리고', '하지만', '그러나', '따라서',
        '있다', '없다', '이다', '아니다', '되다', '하다', '받다', '주다', '드리다',
        '입니다', '습니다', '해요', '죠', '네요', '거예요', '것입니다',
        '안녕하세요', '감사합니다', '여러분', '오늘', '내일', '어제',
        '우리', '저희', '제', '당신', '그', '이', '저', '그것', '이것', '저것',
    }

    # 의료 관련 중요 키워드 (가중치 높음)
    IMPORTANT_MEDICAL_KEYWORDS = {
        '치료', '시술', '수술', '진료', '검사', '진단', '처방', '약물', '재활',
        '피부', '레이저', '보톡스', '필러', '리프팅', '주름', '미백', '홍조',
        '치아', '임플란트', '교정', '충치', '스케일링', '미백',
        '관절', '허리', '목', '어깨', '무릎', '통증', '염증', '디스크',
        '비만', '다이어트', '체중', '지방', '셀룰라이트',
        '백신', '예방접종', '건강검진', '정기검진',
    }

    def analyze(self, text: str) -> Dict:
        """
        텍스트 분석

        Args:
            text: 분석할 텍스트

        Returns:
            분석 결과 딕셔너리
        """
        # 1. 글자수 카운트
        char_count = self._count_characters(text)

        # 2. 키워드 추출 및 분석
        keywords = self._extract_keywords(text)

        # 3. 문장 개수
        sentences = self._count_sentences(text)

        # 4. 단락 개수
        paragraphs = self._count_paragraphs(text)

        return {
            "character_count": char_count,
            "keywords": keywords,
            "sentence_count": sentences,
            "paragraph_count": paragraphs,
            "readability": self._calculate_readability(char_count, sentences),
        }

    def _count_characters(self, text: str) -> Dict[str, int]:
        """글자수 카운트"""
        # 공백 제거
        text_no_space = re.sub(r'\s', '', text)

        # 마크다운 제거
        text_no_markdown = re.sub(r'[#*_`\[\]()]', '', text)

        return {
            "total": len(text),  # 전체 (공백 포함)
            "no_space": len(text_no_space),  # 공백 제외
            "no_markdown": len(re.sub(r'\s', '', text_no_markdown)),  # 마크다운 제외
            "spaces": text.count(' '),  # 공백 수
            "lines": text.count('\n') + 1,  # 줄 수
        }

    def _extract_keywords(self, text: str, top_n: int = 20) -> List[Dict]:
        """
        키워드 추출 및 분석

        Args:
            text: 텍스트
            top_n: 상위 n개 키워드만 반환

        Returns:
            키워드 리스트 (빈도순)
        """
        # 마크다운 제거
        text = re.sub(r'[#*_`]', '', text)

        # 단어 추출 (2글자 이상)
        words = re.findall(r'[가-힣]{2,}', text)

        # 불용어 제거 및 카운트
        meaningful_words = [
            word for word in words
            if word not in self.STOP_WORDS and len(word) >= 2
        ]

        # 빈도 계산
        word_counts = Counter(meaningful_words)

        # 상위 키워드 추출
        keywords = []
        for word, count in word_counts.most_common(top_n):
            # 의료 키워드인지 확인
            is_medical = word in self.IMPORTANT_MEDICAL_KEYWORDS

            keywords.append({
                "word": word,
                "count": count,
                "is_medical": is_medical,
                "importance": "high" if is_medical else "normal"
            })

        return keywords

    def _count_sentences(self, text: str) -> int:
        """문장 개수 카운트"""
        # 마침표, 느낌표, 물음표로 문장 구분
        sentences = re.split(r'[.!?]\s+', text)
        return len([s for s in sentences if s.strip()])

    def _count_paragraphs(self, text: str) -> int:
        """단락 개수 카운트"""
        paragraphs = text.split('\n\n')
        return len([p for p in paragraphs if p.strip()])

    def _calculate_readability(self, char_count: Dict, sentence_count: int) -> str:
        """
        가독성 평가

        Args:
            char_count: 글자수 정보
            sentence_count: 문장 수

        Returns:
            가독성 레벨 (easy/normal/hard)
        """
        if sentence_count == 0:
            return "unknown"

        # 평균 문장 길이
        avg_sentence_length = char_count["no_space"] / sentence_count

        if avg_sentence_length < 30:
            return "easy"  # 쉬움
        elif avg_sentence_length < 50:
            return "normal"  # 보통
        else:
            return "hard"  # 어려움

    def get_keyword_density(self, text: str, keyword: str) -> float:
        """
        특정 키워드의 밀도 계산

        Args:
            text: 텍스트
            keyword: 키워드

        Returns:
            키워드 밀도 (%)
        """
        text_no_space = re.sub(r'\s', '', text)
        keyword_count = text.count(keyword)

        if len(text_no_space) == 0:
            return 0.0

        # 키워드 밀도 = (키워드 글자수 * 출현 횟수) / 전체 글자수 * 100
        density = (len(keyword) * keyword_count) / len(text_no_space) * 100
        return round(density, 2)


# Singleton instance
content_analyzer = ContentAnalyzer()
