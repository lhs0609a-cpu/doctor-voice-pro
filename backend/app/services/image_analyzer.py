"""
Image Analyzer Service
이미지 폴더 자동 인식 및 콘텐츠 매칭
"""

import os
from typing import List, Dict, Optional
from pathlib import Path
import base64
import mimetypes


class ImageAnalyzer:
    """
    이미지 폴더를 분석하여 콘텐츠에 자동 배치
    """

    SUPPORTED_FORMATS = ['.jpg', '.jpeg', '.png', '.gif', '.webp']

    def scan_folder(self, folder_path: str) -> List[Dict]:
        """
        폴더에서 이미지 파일 자동 스캔

        Args:
            folder_path: 이미지 폴더 경로

        Returns:
            이미지 정보 리스트
        """
        images = []

        if not os.path.exists(folder_path):
            raise FileNotFoundError(f"폴더를 찾을 수 없습니다: {folder_path}")

        # 폴더 내 모든 파일 스캔
        for root, dirs, files in os.walk(folder_path):
            for file in sorted(files):  # 파일명 순서대로
                file_path = os.path.join(root, file)
                file_ext = Path(file).suffix.lower()

                if file_ext in self.SUPPORTED_FORMATS:
                    images.append({
                        'path': file_path,
                        'filename': file,
                        'format': file_ext,
                        'size': os.path.getsize(file_path),
                    })

        return images

    def auto_distribute_images(
        self,
        content: str,
        images: List[Dict],
        distribution_strategy: str = 'even'
    ) -> List[Dict]:
        """
        이미지를 콘텐츠 내 적절한 위치에 자동 배치

        Args:
            content: 본문 텍스트
            images: 이미지 리스트
            distribution_strategy: 배치 전략
                - 'even': 균등 분포
                - 'paragraphs': 문단 사이
                - 'ai': AI가 문맥 분석 (추후 구현)

        Returns:
            position이 추가된 이미지 리스트
        """
        if not images:
            return []

        paragraphs = content.split('\n\n')
        total_length = len(content)
        num_images = len(images)

        positioned_images = []

        if distribution_strategy == 'even':
            # 균등 분포: 전체 길이를 이미지 개수+1로 나눔
            interval = total_length // (num_images + 1)

            for i, img in enumerate(images):
                position = interval * (i + 1)
                positioned_images.append({
                    **img,
                    'position': position,
                    'caption': self._generate_caption(img['filename']),
                    'width': 5,  # 기본 너비 (인치)
                })

        elif distribution_strategy == 'paragraphs':
            # 문단 사이에 배치
            current_pos = 0
            img_index = 0

            for i, para in enumerate(paragraphs):
                current_pos += len(para) + 2  # +2 for \n\n

                # 2~3 문단마다 이미지 삽입
                if (i + 1) % 3 == 0 and img_index < num_images:
                    img = images[img_index]
                    positioned_images.append({
                        **img,
                        'position': current_pos,
                        'caption': self._generate_caption(img['filename']),
                        'width': 5,
                    })
                    img_index += 1

            # 남은 이미지는 마지막에 추가
            while img_index < num_images:
                img = images[img_index]
                positioned_images.append({
                    **img,
                    'position': total_length,
                    'caption': self._generate_caption(img['filename']),
                    'width': 5,
                })
                img_index += 1

        return positioned_images

    def _generate_caption(self, filename: str) -> str:
        """
        파일명에서 캡션 자동 생성
        예: "dental_clinic_01.jpg" → "치과 클리닉"
        """
        # 확장자 제거
        name = Path(filename).stem

        # 숫자, 언더스코어 제거
        name = name.replace('_', ' ').replace('-', ' ')

        # 숫자만 있는 부분 제거
        import re
        name = re.sub(r'\b\d+\b', '', name).strip()

        # 빈 문자열이면 기본 캡션
        if not name:
            return "이미지"

        return name

    def convert_to_base64(self, image_path: str) -> str:
        """
        이미지 파일을 base64로 인코딩

        Args:
            image_path: 이미지 파일 경로

        Returns:
            data:image/jpeg;base64,... 형식 문자열
        """
        with open(image_path, 'rb') as img_file:
            img_data = img_file.read()
            img_base64 = base64.b64encode(img_data).decode('utf-8')

        # MIME 타입 자동 감지
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type:
            mime_type = 'image/jpeg'  # 기본값

        return f"data:{mime_type};base64,{img_base64}"

    def prepare_images_for_export(
        self,
        folder_path: str,
        content: str,
        strategy: str = 'paragraphs',
        use_base64: bool = False
    ) -> List[Dict]:
        """
        폴더를 스캔하고 이미지를 콘텐츠에 배치할 준비

        Args:
            folder_path: 이미지 폴더 경로
            content: 본문 내용
            strategy: 배치 전략
            use_base64: True면 base64 인코딩, False면 파일 경로 사용

        Returns:
            워드 문서에 바로 사용 가능한 이미지 데이터
        """
        # 1. 이미지 스캔
        images = self.scan_folder(folder_path)

        if not images:
            return []

        # 2. 자동 배치
        positioned_images = self.auto_distribute_images(content, images, strategy)

        # 3. base64 인코딩 (선택)
        if use_base64:
            for img in positioned_images:
                img['url'] = self.convert_to_base64(img['path'])

        return positioned_images


# 싱글톤 인스턴스
image_analyzer = ImageAnalyzer()
