"""
Claude API 연동 테스트 스크립트
"""
import anthropic
import os
import sys
from dotenv import load_dotenv

# Windows 한글 출력 설정
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# .env 파일 로드
load_dotenv()

def test_claude_api():
    """Claude API 키와 모델 접근성 테스트"""

    api_key = os.getenv("ANTHROPIC_API_KEY")

    print("="*60)
    print("🔍 Claude API 연동 테스트")
    print("="*60)
    print()

    # 1. API 키 확인
    if not api_key:
        print("❌ API 키가 설정되지 않았습니다!")
        print("   .env 파일에 ANTHROPIC_API_KEY를 설정해주세요.")
        return False

    print(f"✅ API 키 확인: {api_key[:20]}...{api_key[-10:]}")
    print()

    # 2. Claude 클라이언트 생성
    try:
        client = anthropic.Anthropic(api_key=api_key)
        print("✅ Claude 클라이언트 생성 성공")
        print()
    except Exception as e:
        print(f"❌ Claude 클라이언트 생성 실패: {e}")
        return False

    # 3. 여러 모델로 테스트
    models_to_test = [
        "claude-sonnet-4-5-20250929",  # 최신 권장 모델
        "claude-3-5-sonnet-20241022",
        "claude-3-5-sonnet-20240620",
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
    ]

    print("="*60)
    print("🧪 모델 접근성 테스트 (간단한 메시지 전송)")
    print("="*60)
    print()

    working_models = []

    for model in models_to_test:
        print(f"테스트 중: {model}...", end=" ")
        try:
            message = client.messages.create(
                model=model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}]
            )
            print("✅ 작동!")
            working_models.append(model)
        except anthropic.NotFoundError as e:
            print(f"❌ 404 - 모델을 찾을 수 없음")
        except anthropic.AuthenticationError as e:
            print(f"❌ 인증 실패 - API 키가 유효하지 않음")
            return False
        except Exception as e:
            print(f"❌ 오류: {type(e).__name__} - {str(e)[:50]}")

    print()
    print("="*60)
    print("📊 테스트 결과 요약")
    print("="*60)
    print()

    if working_models:
        print(f"✅ 사용 가능한 모델 ({len(working_models)}개):")
        for model in working_models:
            print(f"   • {model}")
        print()
        print("💡 권장 사항:")
        print(f"   ai_rewrite_engine.py에서 다음 모델을 사용하세요:")
        print(f"   model=\"{working_models[0]}\"")
    else:
        print("❌ 사용 가능한 모델이 없습니다!")
        print()
        print("💡 해결 방법:")
        print("   1. Anthropic Console에서 API 키를 확인하세요")
        print("   2. API 키에 충분한 크레딧이 있는지 확인하세요")
        print("   3. 새로운 API 키를 생성해보세요")
        print("   4. https://console.anthropic.com/settings/keys")

    print()
    return len(working_models) > 0

if __name__ == "__main__":
    success = test_claude_api()
    exit(0 if success else 1)
