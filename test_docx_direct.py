"""
DOCX 생성 직접 테스트 (백엔드 서버 없이)
"""
import sys
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 백엔드 경로 추가
sys.path.insert(0, 'backend')

from app.services.blog_exporter import blog_exporter

def test_direct_docx_generation():
    """직접 DOCX 생성 테스트"""

    print("="*60)
    print("📝 DOCX 생성 직접 테스트")
    print("="*60 + "\n")

    # 테스트 데이터
    content = """
# 테스트 블로그 포스트

이것은 테스트 콘텐츠입니다.

## 중요한 섹션

여기는 **중요한** 내용이 포함되어 있습니다.

> 이것은 인용구입니다.

- 리스트 아이템 1
- 리스트 아이템 2
- 리스트 아이템 3

일반 문단입니다. 건강검진, 치료, 예방 등의 키워드가 포함되어 있습니다.
    """.strip()

    title = "테스트_워드_다운로드"
    keywords = ["건강검진", "치료", "예방"]
    emphasis_phrases = ["중요한"]

    try:
        print("🔧 DOCX 생성 시작...")
        docx_file = blog_exporter.export_to_docx(
            content=content,
            title=title,
            keywords=keywords,
            emphasis_phrases=emphasis_phrases,
            images=[]
        )

        # 파일 저장
        output_path = "test_output_direct.docx"
        with open(output_path, "wb") as f:
            f.write(docx_file.getvalue())

        file_size = len(docx_file.getvalue())

        print(f"✅ 성공! DOCX 파일 생성 완료")
        print(f"📁 저장 위치: {output_path}")
        print(f"📊 파일 크기: {file_size:,} bytes")
        print("\n💡 다음 단계:")
        print("   1. test_output_direct.docx 파일 열기")
        print("   2. 전체 선택 (Ctrl+A)")
        print("   3. 복사 (Ctrl+C)")
        print("   4. 네이버 블로그에 붙여넣기 (Ctrl+V)")

        return True

    except Exception as e:
        print(f"❌ 실패!")
        print(f"에러 타입: {type(e).__name__}")
        print(f"에러 메시지: {e}")

        import traceback
        print("\n상세 에러:")
        traceback.print_exc()

        return False

if __name__ == "__main__":
    success = test_direct_docx_generation()

    print("\n" + "="*60)
    if success:
        print("✅ 테스트 성공!")
    else:
        print("❌ 테스트 실패!")
    print("="*60)
