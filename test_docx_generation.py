#!/usr/bin/env python3
"""
DOCX 생성 테스트 스크립트
"""
import requests
import json

# API 테스트
url = "https://doctor-voice-pro-backend.fly.dev/api/v1/export/docx"

data = {
    "content": "테스트 본문입니다.\n\n이것은 두 번째 문단입니다.",
    "title": "테스트 제목",
    "keywords": ["테스트", "키워드"],
    "emphasis_phrases": ["두 번째"],
    "images": []
}

print("📝 DOCX 생성 API 테스트 중...")
print(f"URL: {url}")
print(f"Data: {json.dumps(data, ensure_ascii=False, indent=2)}")
print()

try:
    response = requests.post(url, json=data)
    print(f"Status: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")
    print()

    if response.ok:
        print("✅ 성공! DOCX 파일 생성됨")
        print(f"파일 크기: {len(response.content)} bytes")

        # 파일 저장
        with open("test_output.docx", "wb") as f:
            f.write(response.content)
        print("파일 저장됨: test_output.docx")
    else:
        print(f"❌ 실패: {response.status_code}")
        try:
            error_json = response.json()
            print(f"에러 상세:")
            print(json.dumps(error_json, ensure_ascii=False, indent=2))
        except:
            print(f"응답 내용: {response.text[:500]}")

except Exception as e:
    print(f"❌ 요청 실패: {e}")
    import traceback
    traceback.print_exc()
