"""
Medical Law Compliance Checker
의료법 준수 검증 모듈
"""

import re
from typing import List, Dict, Tuple


class MedicalLawChecker:
    """
    의료법 위반 표현 검증 및 대체 표현 제안
    """

    # 의료법 위반 패턴 정의
    VIOLATION_PATTERNS = {
        "절대적_표현": [
            (r"100%\s*(?:완치|치료|효과)", "높은 치료 성공률"),
            (r"(?:반드시|무조건|확실히)\s*(?:낫습니다|치료됩니다|효과)", "치료 효과를 기대할 수 있습니다"),
            (r"(?:절대|완전히)\s*(?:안전|부작용\s*없)", "안전한 치료 방법"),
            (r"완벽한?\s*(?:치료|효과)", "우수한 치료 효과"),
        ],
        "비교_우위": [
            (r"(?:최고|최상|최고급|넘버원|No\.1)", "검증된"),
            (r"세계\s*(?:최초|유일)", "혁신적인"),
            (r"국내\s*(?:최고|1위)", "국내에서도 인정받는"),
            (r"(?:타병원|다른\s*병원).*?(?:보다|보다는)\s*(?:우수|뛰어남)", "전문적인 치료"),
        ],
        "과장_광고": [
            (r"(?:즉시|바로|당장)\s*(?:효과|치료)", "빠른 증상 개선 가능"),
            (r"단\s*\d+(?:일|주|개월).*?(?:완치|완전\s*회복)", "치료 기간은 개인차가 있습니다"),
            (r"(?:특허|독점|유일)", "차별화된"),
            (r"획기적", "효과적인"),
            (r"기적", "놀라운"),
        ],
        "가격_할인": [
            (r"\d+%\s*(?:할인|인하|DC)", "합리적인 비용"),
            (r"(?:이벤트|특가|프로모션).*?\d+\s*원", ""),
            (r"(?:무료|공짜|서비스)", ""),
        ],
        "보장_표현": [
            (r"(?:보장|약속).*?(?:효과|결과)", "기대할 수 있는 효과"),
            (r"(?:누구나|모든\s*사람)\s*(?:효과|치료)", "많은 환자분들이 효과를 경험"),
        ],
    }

    def __init__(self):
        self.compiled_patterns = self._compile_patterns()

    def _compile_patterns(self) -> Dict[str, List[Tuple[re.Pattern, str]]]:
        """
        정규식 패턴 사전 컴파일
        """
        compiled = {}
        for category, patterns in self.VIOLATION_PATTERNS.items():
            compiled[category] = [
                (re.compile(pattern, re.IGNORECASE), alternative)
                for pattern, alternative in patterns
            ]
        return compiled

    def check(self, text: str) -> Dict:
        """
        텍스트에서 의료법 위반 표현 검사

        Args:
            text: 검사할 텍스트

        Returns:
            {
                "is_compliant": bool,
                "violations": [...],
                "warnings": [...]
            }
        """
        violations = []
        warnings = []

        for category, patterns in self.compiled_patterns.items():
            for pattern, alternative in patterns:
                matches = list(pattern.finditer(text))

                for match in matches:
                    violation_data = {
                        "category": category,
                        "text": match.group(),
                        "position": match.span(),
                        "severity": self._get_severity(category),
                        "suggestion": alternative,
                        "context": self._get_context(text, match.span()),
                    }

                    if self._get_severity(category) in ["high", "critical"]:
                        violations.append(violation_data)
                    else:
                        warnings.append(violation_data)

        return {
            "is_compliant": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
            "total_issues": len(violations) + len(warnings),
        }

    def _get_severity(self, category: str) -> str:
        """
        카테고리별 위반 심각도 반환
        """
        severity_map = {
            "절대적_표현": "high",
            "비교_우위": "high",
            "과장_광고": "high",
            "가격_할인": "critical",
            "보장_표현": "high",
        }
        return severity_map.get(category, "medium")

    def _get_context(self, text: str, position: Tuple[int, int], window: int = 50) -> str:
        """
        위반 표현의 문맥 추출
        """
        start, end = position
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)

        context = text[context_start:context_end]
        return context.strip()

    def auto_fix(self, text: str) -> Tuple[str, List[Dict]]:
        """
        위반 표현 자동 수정

        Args:
            text: 수정할 텍스트

        Returns:
            (수정된 텍스트, 수정 내역 리스트)
        """
        fixed_text = text
        changes = []

        for category, patterns in self.compiled_patterns.items():
            for pattern, alternative in patterns:
                matches = list(pattern.finditer(fixed_text))

                # 뒤에서부터 교체 (인덱스 유지)
                for match in reversed(matches):
                    if alternative:  # 대체 표현이 있는 경우만
                        original = match.group()
                        start, end = match.span()

                        # 교체
                        fixed_text = fixed_text[:start] + alternative + fixed_text[end:]

                        changes.append(
                            {
                                "category": category,
                                "original": original,
                                "replaced": alternative,
                                "position": (start, end),
                            }
                        )

        return fixed_text, changes

    def get_compliance_score(self, text: str) -> float:
        """
        의료법 준수 점수 계산 (0-100)

        Args:
            text: 평가할 텍스트

        Returns:
            준수 점수 (높을수록 좋음)
        """
        result = self.check(text)

        if result["is_compliant"]:
            # 경고만 있는 경우
            if result["warnings"]:
                penalty = len(result["warnings"]) * 5
                return max(80, 100 - penalty)
            return 100

        # 위반이 있는 경우
        violation_penalty = len(result["violations"]) * 15
        warning_penalty = len(result["warnings"]) * 5

        score = max(0, 100 - violation_penalty - warning_penalty)
        return score


# Singleton instance
medical_law_checker = MedicalLawChecker()
