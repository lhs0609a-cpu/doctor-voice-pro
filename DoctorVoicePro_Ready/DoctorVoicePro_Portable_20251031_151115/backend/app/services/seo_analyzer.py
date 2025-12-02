"""
SEO Analyzer Service
포스팅 SEO 점수 분석
"""

import re
from typing import Dict, List


class SEOAnalyzer:
    def analyze(self, title: str, content: str, keywords: List[str]) -> Dict:
        """
        포스팅의 SEO 점수 분석

        Returns:
            {
                "overall_score": int (0-100),
                "title_score": int,
                "content_score": int,
                "keyword_score": int,
                "readability_score": int,
                "recommendations": List[str],
            }
        """

        scores = {
            "title_score": self._analyze_title(title, keywords),
            "content_score": self._analyze_content(content),
            "keyword_score": self._analyze_keywords(content, keywords),
            "readability_score": self._analyze_readability(content),
        }

        overall_score = sum(scores.values()) // len(scores)

        recommendations = self._generate_recommendations(title, content, keywords, scores)

        return {
            "overall_score": overall_score,
            **scores,
            "recommendations": recommendations,
        }

    def _analyze_title(self, title: str, keywords: List[str]) -> int:
        """제목 분석 (0-100)"""
        score = 50  # Base score

        # Length check (30-60 characters ideal)
        title_len = len(title)
        if 30 <= title_len <= 60:
            score += 25
        elif title_len < 30:
            score += 10
        elif title_len > 80:
            score -= 10

        # Keyword in title
        if keywords and any(keyword.lower() in title.lower() for keyword in keywords[:3]):
            score += 25

        return min(100, max(0, score))

    def _analyze_content(self, content: str) -> int:
        """콘텐츠 구조 분석 (0-100)"""
        score = 50

        # Length check (800-2000 characters ideal)
        content_len = len(content)
        if 800 <= content_len <= 2000:
            score += 30
        elif 500 <= content_len < 800:
            score += 20
        elif content_len < 500:
            score += 10

        # Paragraph structure
        paragraphs = content.split("\n\n")
        if 3 <= len(paragraphs) <= 10:
            score += 20

        return min(100, max(0, score))

    def _analyze_keywords(self, content: str, keywords: List[str]) -> int:
        """키워드 밀도 분석 (0-100)"""
        if not keywords:
            return 50

        score = 0
        content_lower = content.lower()
        word_count = len(content.split())

        for i, keyword in enumerate(keywords[:5]):
            keyword_count = content_lower.count(keyword.lower())
            density = (keyword_count / word_count) * 100 if word_count > 0 else 0

            # Ideal density: 1-3%
            if 1 <= density <= 3:
                score += 20
            elif 0.5 <= density < 1 or 3 < density <= 5:
                score += 10
            elif density > 0:
                score += 5

        return min(100, max(0, score))

    def _analyze_readability(self, content: str) -> int:
        """가독성 분석 (0-100)"""
        score = 50

        # Sentence count
        sentences = re.split(r'[.!?]+', content)
        sentences = [s for s in sentences if s.strip()]
        sentence_count = len(sentences)

        # Average sentence length
        words = content.split()
        word_count = len(words)

        if sentence_count > 0:
            avg_sentence_length = word_count / sentence_count

            # Ideal: 15-20 words per sentence
            if 15 <= avg_sentence_length <= 20:
                score += 30
            elif 10 <= avg_sentence_length < 15 or 20 < avg_sentence_length <= 25:
                score += 20
            else:
                score += 10

        # Paragraph length variation
        paragraphs = [p for p in content.split("\n\n") if p.strip()]
        if paragraphs:
            para_lengths = [len(p.split()) for p in paragraphs]
            if len(set(para_lengths)) > 1:  # Has variation
                score += 20

        return min(100, max(0, score))

    def _generate_recommendations(
        self, title: str, content: str, keywords: List[str], scores: Dict
    ) -> List[str]:
        """개선 권장사항 생성"""
        recommendations = []

        # Title recommendations
        if scores["title_score"] < 70:
            title_len = len(title)
            if title_len < 30:
                recommendations.append("제목이 너무 짧습니다. 30-60자 사이를 권장합니다.")
            elif title_len > 60:
                recommendations.append("제목이 너무 깁니다. 30-60자 사이를 권장합니다.")

            if keywords and not any(k.lower() in title.lower() for k in keywords[:3]):
                recommendations.append("제목에 주요 키워드를 포함시키세요.")

        # Content recommendations
        if scores["content_score"] < 70:
            content_len = len(content)
            if content_len < 800:
                recommendations.append("본문이 너무 짧습니다. 800-2000자를 권장합니다.")
            elif content_len > 2000:
                recommendations.append("본문이 너무 깁니다. 가독성을 위해 나누는 것을 고려하세요.")

        # Keyword recommendations
        if scores["keyword_score"] < 70:
            recommendations.append("키워드 사용 빈도를 조정하세요. 전체 단어의 1-3%가 이상적입니다.")

        # Readability recommendations
        if scores["readability_score"] < 70:
            recommendations.append("문장 길이를 조절하여 가독성을 높이세요 (15-20단어/문장).")
            recommendations.append("단락을 다양한 길이로 구성하여 리듬감을 주세요.")

        if not recommendations:
            recommendations.append("SEO 최적화가 잘 되어 있습니다!")

        return recommendations


# Singleton
seo_analyzer = SEOAnalyzer()
