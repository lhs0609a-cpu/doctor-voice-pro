"""
네이버 블로그 금칙어 검사 및 자동 대체 서비스
"""

import re
from typing import Dict, List, Tuple


class ForbiddenWordsChecker:
    """네이버 블로그 금칙어 검사기"""

    # 네이버 블로그 금칙어 목록 (의료 관련)
    FORBIDDEN_WORDS = {
        # 효과 과장 금지어
        "100% 치료": "개선 가능",
        "완치": "치료",
        "최고": "우수한",
        "최상": "좋은",
        "No.1": "상위권",
        "1위": "상위권",
        "세계 최초": "혁신적인",
        "획기적": "효과적인",
        "기적": "놀라운 결과",
        "마법": "효과적인",
        "즉시": "빠르게",
        "즉각": "신속하게",
        "100%": "높은 확률로",
        "무조건": "일반적으로",
        "반드시": "대부분",
        "절대": "매우",

        # 비교 광고 금지어
        "타병원 대비": "일반적인 경우 대비",
        "타의원 대비": "일반적인 경우 대비",
        "다른 병원보다": "일반적인 경우 대비",

        # 가격 할인 유도 금지어
        "특가": "합리적인 가격",
        "할인": "상담을 통한 안내",
        "이벤트 가격": "상담 시 안내",
        "프로모션": "상담 시 안내",
        "무료": "별도 비용 없이",

        # 의료법 위반 표현
        "수술 없이": "비수술로",
        "부작용 없음": "부작용이 적은",
        "통증 없음": "통증이 적은",
        "흉터 없음": "흉터가 적은",
        "다운타임 없음": "다운타임이 짧은",
        "100% 안전": "안전한",

        # 환자 유인 금지어
        "지금 바로": "편하신 시간에",
        "서두르세요": "상담받아보세요",
        "얼마 남지 않았습니다": "상담 가능합니다",
        "선착순": "상담 가능",
        "한정": "상담 시 안내",

        # 과장된 효과 표현
        "영구적": "오래 지속되는",
        "평생": "장기간",
        "단 한 번": "적은 횟수의",
        "단 1회": "적은 횟수의",
    }

    # 패턴 기반 금칙어 (정규표현식)
    FORBIDDEN_PATTERNS = [
        (r'(\d+)%\s*효과', r'\1% 수준의 효과'),
        (r'(\d+)%\s*만족', r'높은 만족도'),
        (r'(\d+)만원', r'상담 시 안내'),
        (r'(\d+)원', r'상담 시 안내'),
        (r'\d+회\s*무료', r'상담 시 안내'),
    ]

    def check_and_replace(self, text: str) -> Tuple[str, List[Dict]]:
        """
        텍스트에서 금칙어를 찾아서 대체

        Args:
            text: 검사할 텍스트

        Returns:
            (대체된 텍스트, 변경 내역 리스트)
        """
        replacements = []
        modified_text = text

        # 1. 고정 단어 대체
        for forbidden, replacement in self.FORBIDDEN_WORDS.items():
            if forbidden in modified_text:
                count = modified_text.count(forbidden)
                modified_text = modified_text.replace(forbidden, replacement)
                replacements.append({
                    "original": forbidden,
                    "replaced": replacement,
                    "count": count,
                    "type": "exact_match"
                })

        # 2. 패턴 기반 대체
        for pattern, replacement in self.FORBIDDEN_PATTERNS:
            matches = re.finditer(pattern, modified_text)
            for match in matches:
                original = match.group(0)
                new_text = re.sub(pattern, replacement, original)
                modified_text = modified_text.replace(original, new_text)
                replacements.append({
                    "original": original,
                    "replaced": new_text,
                    "count": 1,
                    "type": "pattern_match"
                })

        return modified_text, replacements

    def check_only(self, text: str) -> List[Dict]:
        """
        텍스트에서 금칙어만 검사 (대체 없이)

        Args:
            text: 검사할 텍스트

        Returns:
            발견된 금칙어 리스트
        """
        found_words = []

        # 1. 고정 단어 검사
        for forbidden, replacement in self.FORBIDDEN_WORDS.items():
            if forbidden in text:
                count = text.count(forbidden)
                found_words.append({
                    "word": forbidden,
                    "suggestion": replacement,
                    "count": count,
                    "type": "exact_match"
                })

        # 2. 패턴 기반 검사
        for pattern, replacement in self.FORBIDDEN_PATTERNS:
            matches = re.finditer(pattern, text)
            for match in matches:
                found_words.append({
                    "word": match.group(0),
                    "suggestion": re.sub(pattern, replacement, match.group(0)),
                    "count": 1,
                    "type": "pattern_match"
                })

        return found_words

    def get_forbidden_words_list(self) -> List[str]:
        """금칙어 목록 반환"""
        return list(self.FORBIDDEN_WORDS.keys())


# Singleton instance
forbidden_words_checker = ForbiddenWordsChecker()
