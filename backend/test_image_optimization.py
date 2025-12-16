"""
이미지 최적화 테스트
네이버 블로그 5MB 제한에 맞게 이미지가 최적화되는지 확인
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.services.blog_exporter import blog_exporter
from PIL import Image
import io

def create_test_image(width: int, height: int, color: tuple = (255, 0, 0)) -> io.BytesIO:
    """
    테스트용 이미지 생성

    Args:
        width: 이미지 너비
        height: 이미지 높이
        color: RGB 색상 (기본값: 빨간색)

    Returns:
        BytesIO 객체
    """
    img = Image.new('RGB', (width, height), color)
    output = io.BytesIO()
    img.save(output, format='PNG')
    output.seek(0)
    return output

def test_image_optimization():
    """이미지 최적화 테스트"""

    print("=" * 60)
    print("이미지 최적화 테스트 시작")
    print("=" * 60)
    print()

    # 테스트 1: 큰 이미지 (3000x2000) - 리사이징 필요
    print("테스트 1: 큰 이미지 (3000x2000px)")
    print("-" * 60)
    large_img = create_test_image(3000, 2000)
    original_size = len(large_img.getvalue())
    print(f"원본 크기: {original_size / (1024 * 1024):.2f}MB")

    optimized = blog_exporter._convert_to_png(large_img)
    optimized_size = len(optimized.getvalue())
    print(f"최적화 후 크기: {optimized_size / (1024 * 1024):.2f}MB")
    print(f"압축률: {(1 - optimized_size / original_size) * 100:.1f}%")
    print()

    # 테스트 2: 중간 크기 이미지 (1920x1080)
    print("테스트 2: 중간 크기 이미지 (1920x1080px)")
    print("-" * 60)
    medium_img = create_test_image(1920, 1080)
    original_size = len(medium_img.getvalue())
    print(f"원본 크기: {original_size / (1024 * 1024):.2f}MB")

    optimized = blog_exporter._convert_to_png(medium_img)
    optimized_size = len(optimized.getvalue())
    print(f"최적화 후 크기: {optimized_size / (1024 * 1024):.2f}MB")
    print(f"압축률: {(1 - optimized_size / original_size) * 100:.1f}%")
    print()

    # 테스트 3: 작은 이미지 (800x600)
    print("테스트 3: 작은 이미지 (800x600px)")
    print("-" * 60)
    small_img = create_test_image(800, 600)
    original_size = len(small_img.getvalue())
    print(f"원본 크기: {original_size / (1024 * 1024):.2f}MB")

    optimized = blog_exporter._convert_to_png(small_img)
    optimized_size = len(optimized.getvalue())
    print(f"최적화 후 크기: {optimized_size / (1024 * 1024):.2f}MB")
    print(f"압축률: {(1 - optimized_size / original_size) * 100:.1f}%")
    print()

    # 테스트 4: DOCX 파일 크기 확인
    print("테스트 4: DOCX 파일 전체 크기 확인")
    print("-" * 60)

    # 여러 이미지를 포함한 DOCX 생성
    test_content = """
    테스트 블로그 포스트입니다.

    이 포스트는 여러 개의 이미지를 포함하고 있습니다.
    각 이미지는 최적화되어 전체 파일 크기가 5MB 이하로 유지됩니다.

    네이버 블로그에 업로드할 수 있는 크기입니다.
    """

    test_images = []
    for i in range(3):
        img = create_test_image(2000, 1500, color=(255, i*50, i*50))
        test_images.append({
            "url": f"data:image/png;base64,{img.getvalue().hex()}",
            "caption": f"테스트 이미지 {i+1}",
            "width": 5
        })

    docx_file = blog_exporter.export_to_docx(
        content=test_content,
        title="테스트 포스트",
        images=test_images
    )

    docx_size = len(docx_file.getvalue())
    print(f"DOCX 파일 크기: {docx_size / (1024 * 1024):.2f}MB")

    if docx_size < 5 * 1024 * 1024:
        print("✅ 네이버 블로그 업로드 가능 (5MB 이하)")
    else:
        print("❌ 파일이 너무 큽니다 (5MB 초과)")

    print()
    print("=" * 60)
    print("테스트 완료!")
    print("=" * 60)

if __name__ == "__main__":
    test_image_optimization()
