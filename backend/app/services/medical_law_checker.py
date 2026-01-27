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

    # 부정문 패턴 (거짓양성 방지용) - P0 버그 수정
    NEGATION_PATTERNS = [
        r"(?:아닙니다|않습니다|않아요|않다|아니다|없습니다|없다|없어요)",
        r"(?:불가능|금지|위반|위법|불법)",
        r"(?:하면\s*안\s*됩니다|하지\s*마세요|하지\s*않|피해야)",
        r"(?:~이\s*아닌|~가\s*아닌|은\s*아닌|는\s*아닌)",
    ]

    # 인용문 패턴 (법조문 설명, 예시 등)
    QUOTATION_PATTERNS = [
        r"['\"].*?['\"]",  # 따옴표로 감싸진 텍스트
        r"「.*?」",  # 법조문 인용
        r"『.*?』",  # 큰 따옴표
        r"의료법.*?(?:금지|위반|규정)",  # 법률 설명 문맥
    ]

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
        self.compiled_negation_patterns = self._compile_negation_patterns()
        self.compiled_quotation_patterns = self._compile_quotation_patterns()

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

    def _compile_negation_patterns(self) -> List[re.Pattern]:
        """
        부정문 패턴 사전 컴파일 - P0 버그 수정
        """
        return [re.compile(pattern, re.IGNORECASE) for pattern in self.NEGATION_PATTERNS]

    def _compile_quotation_patterns(self) -> List[re.Pattern]:
        """
        인용문 패턴 사전 컴파일 - P0 버그 수정
        """
        return [re.compile(pattern, re.IGNORECASE) for pattern in self.QUOTATION_PATTERNS]

    def _extract_sentence(self, text: str, position: int) -> str:
        """
        주어진 위치가 포함된 문장을 추출 - P0 버그 수정

        Args:
            text: 전체 텍스트
            position: 문장을 찾을 위치

        Returns:
            해당 위치가 포함된 문장
        """
        # 문장 구분자 정의 (마침표, 물음표, 느낌표, 줄바꿈)
        sentence_delimiters = '.?!。\n'

        # 문장 시작 위치 찾기
        sentence_start = position
        while sentence_start > 0:
            if text[sentence_start - 1] in sentence_delimiters:
                break
            sentence_start -= 1

        # 문장 끝 위치 찾기
        sentence_end = position
        while sentence_end < len(text):
            if text[sentence_end] in sentence_delimiters:
                sentence_end += 1  # 구분자 포함
                break
            sentence_end += 1

        return text[sentence_start:sentence_end].strip()

    def _is_negation_context(self, text: str, match_position: Tuple[int, int], window: int = 30) -> bool:
        """
        부정문 문맥인지 확인 - P0 버그 수정 (거짓양성 방지)

        P0 개선: 30자 윈도우 → 문장 단위 컨텍스트 분석
        - 기존: "100% 효과를 보장하기는 어렵습니다" → 30자 밖이면 위반 처리
        - 개선: 문장 전체에서 부정 표현 검색

        Args:
            text: 전체 텍스트
            match_position: 매칭된 위반 표현의 위치 (start, end)
            window: 문맥 확인 범위 (fallback용, 기본값 유지)

        Returns:
            True면 부정문 문맥 (위반이 아님)
        """
        start, end = match_position

        # P0 Fix: 문장 단위로 컨텍스트 추출
        sentence = self._extract_sentence(text, start)

        # 문장 내에서 부정문 패턴 검사
        for pattern in self.compiled_negation_patterns:
            if pattern.search(sentence):
                return True

        # Fallback: 문장 추출이 너무 짧으면 기존 윈도우 방식도 함께 사용
        if len(sentence) < 20:
            context_start = max(0, start - window)
            context_end = min(len(text), end + window)
            context = text[context_start:context_end]
            for pattern in self.compiled_negation_patterns:
                if pattern.search(context):
                    return True

        return False

    def _is_quotation_context(self, text: str, match_position: Tuple[int, int]) -> bool:
        """
        인용문/법조문 설명 문맥인지 확인 - P0 버그 수정 (거짓양성 방지)

        Args:
            text: 전체 텍스트
            match_position: 매칭된 위반 표현의 위치 (start, end)

        Returns:
            True면 인용문 문맥 (위반이 아님)
        """
        start, end = match_position

        for pattern in self.compiled_quotation_patterns:
            for match in pattern.finditer(text):
                quote_start, quote_end = match.span()
                # 위반 표현이 인용문 안에 있는지 확인
                if quote_start <= start and end <= quote_end:
                    return True

        return False

    # 법적 면책조항
    DISCLAIMER = {
        "title": "⚠️ 의료법 검증 면책조항",
        "message": "본 검증 결과는 AI 기반 참고 자료이며, 법적 효력이 없습니다. 의료광고 관련 법률 준수 여부의 최종 판단과 책임은 사용자(광고주)에게 있습니다.",
        "details": [
            "본 서비스는 의료법 위반 가능성이 있는 표현을 탐지하여 참고 정보를 제공합니다.",
            "검증 결과가 '통과'라도 실제 의료광고심의위원회 심의 결과와 다를 수 있습니다.",
            "의료법, 의료광고 심의규정은 수시로 변경될 수 있으며, 본 서비스가 최신 법령을 완벽히 반영하지 못할 수 있습니다.",
            "중요한 광고물은 반드시 전문 법률 자문 또는 공식 심의 절차를 거치시기 바랍니다.",
        ],
        "penalty_info": "의료법 위반 시 과태료 최대 300만원, 반복 위반 시 영업정지 처분이 가능합니다.",
        "reference_url": "https://www.mohw.go.kr",
    }

    def check(self, text: str) -> Dict:
        """
        텍스트에서 의료법 위반 표현 검사

        Args:
            text: 검사할 텍스트

        Returns:
            {
                "is_compliant": bool,
                "violations": [...],
                "warnings": [...],
                "skipped": [...],  # 부정문/인용문으로 스킵된 항목
                "disclaimer": {...}
            }
        """
        violations = []
        warnings = []
        skipped = []  # P0 버그 수정: 거짓양성 추적

        for category, patterns in self.compiled_patterns.items():
            for pattern, alternative in patterns:
                matches = list(pattern.finditer(text))

                for match in matches:
                    match_position = match.span()

                    # P0 버그 수정: 부정문 문맥 확인 (거짓양성 방지)
                    if self._is_negation_context(text, match_position):
                        skipped.append({
                            "category": category,
                            "text": match.group(),
                            "position": match_position,
                            "reason": "negation_context",
                            "context": self._get_context(text, match_position),
                        })
                        continue

                    # P0 버그 수정: 인용문 문맥 확인 (거짓양성 방지)
                    if self._is_quotation_context(text, match_position):
                        skipped.append({
                            "category": category,
                            "text": match.group(),
                            "position": match_position,
                            "reason": "quotation_context",
                            "context": self._get_context(text, match_position),
                        })
                        continue

                    violation_data = {
                        "category": category,
                        "text": match.group(),
                        "position": match_position,
                        "severity": self._get_severity(category),
                        "suggestion": alternative,
                        "context": self._get_context(text, match_position),
                    }

                    if self._get_severity(category) in ["high", "critical"]:
                        violations.append(violation_data)
                    else:
                        warnings.append(violation_data)

        return {
            "is_compliant": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
            "skipped": skipped,  # P0: 거짓양성으로 스킵된 항목
            "total_issues": len(violations) + len(warnings),
            "disclaimer": self.DISCLAIMER,
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

                        # P0 버그 수정: 부정문/인용문 문맥은 수정하지 않음
                        if self._is_negation_context(fixed_text, (start, end)):
                            continue
                        if self._is_quotation_context(fixed_text, (start, end)):
                            continue

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
