"""
블로그 내보내기 기능 테스트 스크립트
워드 문서(.docx) 생성 예제
"""

import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.blog_exporter import blog_exporter


def test_export_simple():
    """간단한 예제"""
    print("📝 테스트 1: 간단한 블로그 포스트")

    content = """
치아 건강을 위해서는 정기적인 검진이 중요합니다.

특히 6개월마다 스케일링을 받으시는 것을 권장드립니다.
치석이 쌓이면 잇몸 질환으로 이어질 수 있기 때문입니다.

> 전문의 조언: 하루 3번, 3분씩 양치질하세요.

## 올바른 양치 방법

- 칫솔을 45도 각도로 기울이기
- 잇몸에서 치아 방향으로 쓸어내리기
- 혀도 꼭 닦기

매일 꾸준히 관리하시면 평생 건강한 치아를 유지할 수 있습니다.
    """.strip()

    title = "치아 건강 관리의 모든 것"
    keywords = ["검진", "스케일링", "양치질", "건강"]
    emphasis_phrases = ["6개월마다", "하루 3번"]

    # DOCX 생성
    docx_file = blog_exporter.export_to_docx(
        content=content,
        title=title,
        keywords=keywords,
        emphasis_phrases=emphasis_phrases,
    )

    # 파일 저장
    output_path = "test_simple_blog.docx"
    with open(output_path, "wb") as f:
        f.write(docx_file.getvalue())

    print(f"✅ 파일 생성 완료: {output_path}")
    print(f"   - 제목: {title}")
    print(f"   - 키워드 강조: {', '.join(keywords)}")
    print(f"   - 하이라이트: {', '.join(emphasis_phrases)}")
    print()


def test_export_with_images():
    """이미지 포함 예제"""
    print("📝 테스트 2: 이미지 포함 블로그 포스트")

    content = """
임플란트 시술은 자연 치아와 가장 유사한 치료 방법입니다.

시술 과정은 크게 3단계로 나뉩니다:

## 1단계: 임플란트 식립

먼저 잇몸을 절개하고 턱뼈에 임플란트를 심습니다.
이 과정에서 국소마취를 하므로 통증은 거의 없습니다.

## 2단계: 골유착 기간

임플란트와 뼈가 결합하는 기간으로 보통 3-6개월이 소요됩니다.
이 기간 동안 정기적인 검진이 필요합니다.

## 3단계: 보철물 장착

최종적으로 크라운(인공 치아)을 임플란트에 연결합니다.

> 중요: 시술 후 관리가 성공의 핵심입니다!

## 시술 후 주의사항

- 딱딱한 음식 피하기 (최소 1주일)
- 금연 필수
- 정기 검진 받기

적절한 관리를 하시면 10년 이상 사용 가능합니다.
    """.strip()

    title = "임플란트 시술 완벽 가이드"
    keywords = ["임플란트", "시술", "골유착", "검진"]
    emphasis_phrases = ["3-6개월", "10년 이상", "금연 필수"]

    # 이미지 정보 (실제 파일이 없어도 위치 정보만으로 테스트)
    images = [
        {
            "position": 150,
            "caption": "임플란트 구조 설명",
            "width": 5,
        },
        {
            "position": 600,
            "caption": "시술 과정 3단계",
            "width": 6,
        },
    ]

    # DOCX 생성
    docx_file = blog_exporter.export_to_docx(
        content=content,
        title=title,
        keywords=keywords,
        emphasis_phrases=emphasis_phrases,
        images=images,
    )

    # 파일 저장
    output_path = "test_implant_blog.docx"
    with open(output_path, "wb") as f:
        f.write(docx_file.getvalue())

    print(f"✅ 파일 생성 완료: {output_path}")
    print(f"   - 제목: {title}")
    print(f"   - 이미지: {len(images)}개")
    print()


def test_export_html():
    """HTML 내보내기 예제"""
    print("📝 테스트 3: 네이버 블로그용 HTML")

    content = """
여름철 건강 관리, 이것만 알면 됩니다!

## 수분 섭취가 최우선

하루 2리터 이상의 물을 마시는 것이 중요합니다.
특히 운동 후에는 꼭 수분을 보충하세요.

> 팁: 물병을 항상 가지고 다니세요!

## 자외선 차단

외출 시 자외선 차단제는 필수입니다.
SPF 30 이상 제품을 2시간마다 발라주세요.

건강한 여름 보내세요!
    """.strip()

    title = "여름철 건강 관리 꿀팁"
    keywords = ["수분", "자외선", "건강"]
    emphasis_phrases = ["2리터 이상", "SPF 30"]

    # HTML 생성
    html = blog_exporter.export_to_naver_html(
        content=content,
        title=title,
        keywords=keywords,
        emphasis_phrases=emphasis_phrases,
    )

    # HTML 파일 저장
    output_path = "test_summer_blog.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ 파일 생성 완료: {output_path}")
    print(f"   - HTML 길이: {len(html)} 문자")
    print()
    print("📋 HTML 미리보기:")
    print(html[:500] + "...")
    print()


def main():
    print("=" * 60)
    print("블로그 내보내기 기능 테스트")
    print("=" * 60)
    print()

    try:
        test_export_simple()
        test_export_with_images()
        test_export_html()

        print("=" * 60)
        print("✅ 모든 테스트 완료!")
        print("=" * 60)
        print()
        print("📂 생성된 파일:")
        print("   - test_simple_blog.docx (기본 예제)")
        print("   - test_implant_blog.docx (이미지 포함)")
        print("   - test_summer_blog.html (HTML 버전)")
        print()
        print("🚀 사용 방법:")
        print("   1. .docx 파일을 워드로 열기")
        print("   2. 전체 선택 (Ctrl+A)")
        print("   3. 복사 (Ctrl+C)")
        print("   4. 블로그에 붙여넣기 (Ctrl+V)")
        print()

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
