"""
키워드 추출 로직 테스트 스크립트
"""

import sys
sys.path.insert(0, '.')

from app.services.seo_optimizer import seo_optimizer

# 테스트 케이스
test_cases = [
    "만성 두드러기 병원 효과 없다면 OOO부터 확인하세요",
    "항문주변습진 계속 재발한다면 'OO' 강화하세요",
    "항문 주변 따가움 '이렇게' 하면 치료 어렵지않습니다",
    "서울 아토피 피부과 대신 혈액치료, 무슨 원리일까?",
]

expected_results = [
    "만성두드러기병원",
    "항문주변습진",
    "항문주변따가움",
    "서울아토피피부과",
]

print("=" * 60)
print("키워드 추출 테스트")
print("=" * 60)
print()

for i, (title, expected) in enumerate(zip(test_cases, expected_results), 1):
    keyword = seo_optimizer.extract_keyword_from_title(title)
    status = "OK" if keyword == expected else "FAIL"

    print(f"Test {i}: {status}")
    print(f"  Title: {title}")
    print(f"  Expected: {expected}")
    print(f"  Actual: {keyword}")
    print()

print("=" * 60)
