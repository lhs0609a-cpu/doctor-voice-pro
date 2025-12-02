"""
DOCX Export API Test
"""
import requests
import json
import os
import sys

# Windows 환경에서 UTF-8 출력 설정
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 백엔드 URL (환경에 맞게 설정)
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8010")

def test_docx_export():
    """워드 다운로드 API 테스트"""

    url = f"{BACKEND_URL}/api/v1/export/docx"

    # 테스트 데이터
    payload = {
        "content": """
# 테스트 블로그 포스트

이것은 테스트 콘텐츠입니다.

## 중요한 섹션

여기는 **중요한** 내용이 포함되어 있습니다.

> 이것은 인용구입니다.

- 리스트 아이템 1
- 리스트 아이템 2
- 리스트 아이템 3

일반 문단입니다. 건강검진, 치료, 예방 등의 키워드가 포함되어 있습니다.
        """.strip(),
        "title": "테스트_워드_다운로드",
        "keywords": ["건강검진", "치료", "예방"],
        "emphasis_phrases": ["중요한"],
        "images": []
    }

    print(f"🔍 테스트 URL: {url}")
    print(f"📝 요청 데이터:\n{json.dumps(payload, indent=2, ensure_ascii=False)}")
    print("\n" + "="*60)

    try:
        print("📡 API 호출 중...")
        response = requests.post(
            url,
            json=payload,
            timeout=30,
            headers={"Content-Type": "application/json"}
        )

        print(f"✅ 응답 상태 코드: {response.status_code}")
        print(f"📋 응답 헤더:")
        for key, value in response.headers.items():
            print(f"  {key}: {value}")

        if response.status_code == 200:
            # DOCX 파일 저장
            output_path = "test_output.docx"
            with open(output_path, "wb") as f:
                f.write(response.content)

            file_size = len(response.content)
            print(f"\n✅ 성공! DOCX 파일 생성됨")
            print(f"📁 저장 위치: {os.path.abspath(output_path)}")
            print(f"📊 파일 크기: {file_size:,} bytes")

            return True
        else:
            print(f"\n❌ 실패! 상태 코드: {response.status_code}")
            print(f"📄 응답 내용:")

            # JSON 응답인지 확인
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' in content_type:
                try:
                    error_data = response.json()
                    print(json.dumps(error_data, indent=2, ensure_ascii=False))
                except:
                    print(response.text)
            else:
                print(response.text[:500])

            return False

    except requests.exceptions.ConnectionError as e:
        print(f"\n❌ 연결 오류: 백엔드 서버가 실행 중인지 확인하세요")
        print(f"   URL: {url}")
        print(f"   에러: {e}")
        return False

    except requests.exceptions.Timeout:
        print(f"\n❌ 타임아웃: 요청 시간이 30초를 초과했습니다")
        return False

    except Exception as e:
        print(f"\n❌ 예외 발생: {type(e).__name__}")
        print(f"   메시지: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("="*60)
    print("📝 네이버 블로그 워드 다운로드 API 테스트")
    print("="*60 + "\n")

    success = test_docx_export()

    print("\n" + "="*60)
    if success:
        print("✅ 테스트 성공!")
        print("\n💡 다음 단계:")
        print("   1. test_output.docx 파일 열기")
        print("   2. 전체 선택 (Ctrl+A)")
        print("   3. 복사 (Ctrl+C)")
        print("   4. 네이버 블로그에 붙여넣기 (Ctrl+V)")
    else:
        print("❌ 테스트 실패!")
        print("\n🔧 문제 해결:")
        print("   1. 백엔드 서버가 실행 중인지 확인")
        print("   2. 위 에러 메시지 확인")
        print("   3. 백엔드 로그 확인")
    print("="*60)
