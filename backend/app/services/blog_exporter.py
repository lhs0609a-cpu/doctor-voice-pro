"""
Blog Exporter Service
블로그 복붙용 문서 생성 (DOCX, HTML)
"""

from docx import Document
from docx.shared import RGBColor, Pt, Inches
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml.shared import OxmlElement
from docx.oxml.ns import qn
from typing import List, Dict, Optional
import re
import io
import base64
from PIL import Image


class BlogExporter:
    """
    블로그 복붙용 문서 생성 서비스
    """

    def __init__(self):
        # 강조 색상 팔레트
        self.highlight_colors = {
            "primary": RGBColor(255, 107, 107),  # 빨강
            "secondary": RGBColor(74, 144, 226),  # 파랑
            "success": RGBColor(34, 197, 94),  # 초록
            "warning": RGBColor(251, 191, 36),  # 노랑
            "info": RGBColor(168, 85, 247),  # 보라
        }

    def export_to_docx(
        self,
        content: str,
        title: str = "",
        images: Optional[List[Dict]] = None,
        keywords: Optional[List[str]] = None,
        emphasis_phrases: Optional[List[str]] = None,
        place_url: Optional[str] = None,
        place_name: Optional[str] = None,
    ) -> io.BytesIO:
        """
        워드 문서 생성 (네이버 블로그 복붙용)

        Args:
            content: 본문 내용
            title: 글 제목
            images: 이미지 리스트 [{"url": "...", "position": 100, "caption": "..."}]
            keywords: 강조할 키워드 리스트
            emphasis_phrases: 하이라이트할 문구 리스트

        Returns:
            BytesIO 객체 (워드 파일)
        """
        doc = Document()

        # 기본 스타일 설정 - 영문 폰트 이름만 사용 (인코딩 문제 해결)
        style = doc.styles['Normal']
        font = style.font
        # Arial Unicode MS는 한글을 포함한 다국어 지원
        # 또는 Calibri도 한글 잘 표시됨
        font.name = 'Arial'
        font.size = Pt(11)

        # 1. 제목은 워드에 포함하지 않음
        # 네이버 블로그는 제목 입력창이 별도로 있으므로,
        # 워드 파일에는 본문만 포함하여 복사-붙여넣기 시 깔끔하게 처리
        # (제목은 사용자가 네이버 블로그 제목란에 직접 입력)

        # 2. 본문 처리
        paragraphs = [p for p in content.split('\n\n') if p.strip()]
        images_list = images or []
        total_paras = len(paragraphs)

        # 이미지 삽입 위치 계산: 문단을 균등하게 나눔
        if images_list and total_paras > 0:
            # 예: 10개 문단, 4개 이미지 -> 2, 4, 6, 8번째 문단 뒤에 삽입
            # Keep at least one text paragraph between images and avoid placing
            # a run of images at the beginning or end of the article.
            usable = max(1, total_paras - 1)
            image_count = min(len(images_list), max(1, usable // 2))
            image_positions = [
                max(1, min(total_paras - 1, round((i + 1) * total_paras / (image_count + 1))))
                for i in range(image_count)
            ]
            image_positions = sorted(set(image_positions))
        else:
            image_positions = []

        img_index = 0
        for para_index, para_text in enumerate(paragraphs):
            # 인용구 감지
            if para_text.strip().startswith('>'):
                self._add_quote(doc, para_text.replace('>', '').strip())
            # 제목 감지 (##)
            elif para_text.strip().startswith('##'):
                heading_text = para_text.replace('#', '').strip()
                h2 = doc.add_heading(heading_text, level=2)
                h2.runs[0].font.color.rgb = RGBColor(52, 73, 94)
            # 리스트 감지
            elif para_text.strip().startswith(('- ', '* ', '• ')):
                self._add_bullet_list(doc, para_text)
            # 일반 문단
            else:
                self._add_styled_paragraph(
                    doc, para_text, keywords, emphasis_phrases
                )

            # 이미지 삽입 (계산된 위치에서)
            if img_index < len(image_positions) and para_index + 1 == image_positions[img_index]:
                if img_index < len(images_list):
                    self._add_image_to_doc(doc, images_list[img_index])
                img_index += 1

        # 3. 남은 이미지 마지막에 추가
        while img_index < len(images_list):
            self._add_image_to_doc(doc, images_list[img_index])
            img_index += 1

        if place_url:
            self._add_place_link(doc, place_url, place_name or "네이버 플레이스에서 위치 확인")

        # 파일을 메모리에 저장
        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)

        # 파일 크기 검증 (네이버 블로그 5MB 제한)
        file_size = len(file_stream.getvalue())
        file_size_mb = file_size / (1024 * 1024)
        print(f"📄 DOCX 파일 크기: {file_size_mb:.2f}MB")

        if file_size_mb > 5.0:
            print(f"⚠️ 경고: 파일 크기가 5MB를 초과했습니다 ({file_size_mb:.2f}MB)")
            print("   네이버 블로그 업로드 시 문제가 발생할 수 있습니다.")
        else:
            print(f"✅ 파일 크기 OK: 네이버 블로그 업로드 가능")

        return file_stream

    def _add_place_link(self, doc: Document, url: str, label: str) -> None:
        """Append a clickable place link at the end of the document."""
        paragraph = doc.add_paragraph()
        paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        run = paragraph.add_run("📍 ")
        run.font.size = Pt(10)
        hyperlink = OxmlElement("w:hyperlink")
        hyperlink.set(qn("r:id"), self._add_hyperlink_relationship(doc, url))
        link_run = OxmlElement("w:r")
        properties = OxmlElement("w:rPr")
        color = OxmlElement("w:color")
        color.set(qn("w:val"), "0563C1")
        properties.append(color)
        underline = OxmlElement("w:u")
        underline.set(qn("w:val"), "single")
        properties.append(underline)
        link_run.append(properties)
        text = OxmlElement("w:t")
        text.text = label
        link_run.append(text)
        hyperlink.append(link_run)
        paragraph._p.append(hyperlink)

    @staticmethod
    def _add_hyperlink_relationship(doc: Document, url: str) -> str:
        return doc.part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)

    def _add_styled_paragraph(
        self,
        doc: Document,
        text: str,
        keywords: Optional[List[str]] = None,
        emphasis_phrases: Optional[List[str]] = None,
    ):
        """
        스타일이 적용된 문단 추가 (네이버 블로그 최적화)
        - 텍스트 색상 대신 형광펜 사용 (네이버가 색상을 무시하기 때문)
        - 볼드 + 형광펜 조합으로 강조
        """
        p = doc.add_paragraph()

        # 키워드와 강조 문구를 하나의 리스트로 통합
        highlight_terms = []
        if keywords:
            highlight_terms.extend([(kw, 'keyword') for kw in keywords])
        if emphasis_phrases:
            highlight_terms.extend([(phrase, 'emphasis') for phrase in emphasis_phrases])

        # 길이 순으로 정렬 (긴 것부터 - 중복 매칭 방지)
        highlight_terms.sort(key=lambda x: len(x[0]), reverse=True)

        if not highlight_terms:
            # 강조할 것이 없으면 그냥 추가
            p.add_run(text)
            return

        # 텍스트를 분할하여 스타일 적용
        remaining_text = text
        processed_text = ""

        while remaining_text:
            found_match = False

            for term, term_type in highlight_terms:
                if term.lower() in remaining_text.lower():
                    # 대소문자 무시하고 찾기
                    idx = remaining_text.lower().find(term.lower())

                    # 매칭 전 텍스트
                    before = remaining_text[:idx]
                    if before:
                        run = p.add_run(before)

                    # 매칭된 텍스트 (원본 케이스 유지)
                    matched = remaining_text[idx:idx + len(term)]
                    run = p.add_run(matched)

                    if term_type == 'keyword':
                        # 키워드: 노란 형광펜 + 볼드 (네이버 블로그 최적화)
                        run.bold = True
                        run.font.highlight_color = 7  # Yellow - 네이버에서 잘 보임
                    else:
                        # 강조 문구: 주황 형광펜 + 볼드
                        run.font.highlight_color = 12  # Bright Green (눈에 띄게)
                        run.bold = True

                    # 나머지 텍스트
                    remaining_text = remaining_text[idx + len(term):]
                    found_match = True
                    break

            if not found_match:
                # 더 이상 매칭되는 것이 없으면 나머지 추가
                p.add_run(remaining_text)
                break

    def _add_quote(self, doc: Document, text: str):
        """
        인용구 추가
        """
        quote = doc.add_paragraph(text)
        quote.style = 'Intense Quote'

        # 왼쪽 테두리 추가 (인용구 스타일)
        pPr = quote._element.get_or_add_pPr()
        pBdr = OxmlElement('w:pBdr')

        left = OxmlElement('w:left')
        left.set(qn('w:val'), 'single')
        left.set(qn('w:sz'), '12')  # 두께
        left.set(qn('w:space'), '4')
        left.set(qn('w:color'), '4A90E2')  # 파란색
        pBdr.append(left)
        pPr.append(pBdr)

        # 배경색 (연한 회색)
        shd = OxmlElement('w:shd')
        shd.set(qn('w:fill'), 'F0F0F0')
        pPr.append(shd)

    def _add_bullet_list(self, doc: Document, text: str):
        """
        불릿 리스트 추가
        """
        items = text.split('\n')
        for item in items:
            item_text = re.sub(r'^[\s\-\*\•]+', '', item).strip()
            if item_text:
                doc.add_paragraph(item_text, style='List Bullet')

    def _convert_to_png(self, img_source, max_width: int = 1200, quality: int = 85) -> io.BytesIO:
        """
        이미지를 최적화하여 PNG/JPEG 형식으로 변환 (네이버 블로그 5MB 제한 대응)

        네이버 블로그는 EMF, WebP 등 일부 형식을 지원하지 않음
        이미지 리사이징 + 압축으로 파일 크기를 5MB 이하로 최적화

        Args:
            img_source: 이미지 소스 (파일 경로 또는 BytesIO)
            max_width: 최대 너비 (기본값: 1200px - 네이버 블로그 최적)
            quality: JPEG 품질 (1-95, 기본값: 85)

        Returns:
            최적화된 이미지 BytesIO
        """
        try:
            # 이미지 열기
            if isinstance(img_source, str):
                # 파일 경로
                img = Image.open(img_source)
            else:
                # BytesIO 또는 bytes
                img = Image.open(img_source)

            # 1. 이미지 리사이징 (큰 이미지는 축소)
            original_width, original_height = img.size
            if original_width > max_width:
                # 비율 유지하며 리사이징
                ratio = max_width / original_width
                new_height = int(original_height * ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                print(f"✅ 이미지 리사이징: {original_width}x{original_height} → {max_width}x{new_height}")

            # 2. RGBA를 RGB로 변환 (투명도 처리)
            if img.mode in ('RGBA', 'LA', 'P'):
                # 흰색 배경에 합성
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            # 3. JPEG로 저장 (PNG보다 훨씬 작은 파일 크기)
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=quality, optimize=True)
            output.seek(0)

            # 파일 크기 확인
            file_size = len(output.getvalue())
            file_size_mb = file_size / (1024 * 1024)
            print(f"✅ 이미지 최적화 완료: {file_size_mb:.2f}MB (품질: {quality})")

            # 4. 만약 파일이 너무 크면 (1MB 이상) 더 압축
            if file_size > 1 * 1024 * 1024:  # 1MB
                print(f"⚠️ 파일이 큼 ({file_size_mb:.2f}MB), 추가 압축 진행...")
                output = io.BytesIO()
                # 품질을 낮춰서 다시 저장
                img.save(output, format='JPEG', quality=70, optimize=True)
                output.seek(0)
                file_size = len(output.getvalue())
                file_size_mb = file_size / (1024 * 1024)
                print(f"✅ 추가 압축 완료: {file_size_mb:.2f}MB (품질: 70)")

            return output

        except Exception as e:
            print(f"⚠️ 이미지 변환 실패: {e}")
            raise

    def _add_image_to_doc(self, doc: Document, img_data: Dict):
        """
        이미지 추가 (JPEG 형식으로 최적화하여 네이버 블로그 5MB 제한 대응)

        Args:
            img_data: {"url": "...", "caption": "...", "width": 5}
        """
        try:
            img_stream = None
            url = img_data.get('url', '')

            # URL이 base64인 경우
            if url.startswith('data:image'):
                # base64 디코딩
                img_base64 = url.split(',')[1]
                img_bytes = base64.b64decode(img_base64)
                # PNG로 변환
                img_stream = io.BytesIO(img_bytes) if url.lower().startswith('data:image/gif') else self._convert_to_png(io.BytesIO(img_bytes))

            # P3 Fix: HTTP/HTTPS URL 이미지 다운로드
            elif url.startswith(('http://', 'https://')):
                try:
                    import requests
                    response = requests.get(url, timeout=10, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    })
                    if response.status_code == 200:
                        img_bytes = response.content
                        content_type = response.headers.get('content-type', '').lower()
                        is_gif = 'gif' in content_type or url.lower().split('?')[0].endswith('.gif')
                        img_stream = io.BytesIO(img_bytes) if is_gif else self._convert_to_png(io.BytesIO(img_bytes))
                    else:
                        print(f"⚠️ 이미지 다운로드 실패 (HTTP {response.status_code}): {url}")
                except Exception as e:
                    print(f"⚠️ 이미지 다운로드 오류: {url} - {e}")

            elif img_data.get('path'):
                # 로컬 파일 경로 - PNG로 변환
                if str(img_data['path']).lower().endswith('.gif'):
                    with open(img_data['path'], 'rb') as gif_file:
                        img_stream = io.BytesIO(gif_file.read())
                else:
                    img_stream = self._convert_to_png(img_data['path'])

            if img_stream:
                width = img_data.get('width', 5)
                doc.add_picture(img_stream, width=Inches(width))

            # 캡션 추가
            if img_data.get('caption'):
                caption = doc.add_paragraph(img_data['caption'])
                caption.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
                caption.runs[0].font.size = Pt(9)
                caption.runs[0].font.color.rgb = RGBColor(128, 128, 128)

            # 이미지 후 빈 줄
            doc.add_paragraph()

        except Exception as e:
            print(f"❌ 이미지 추가 실패: {e}")
            # 이미지 추가 실패 시 설명만 추가
            p = doc.add_paragraph(f"[이미지: {img_data.get('caption', '이미지')}]")
            p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

    def export_to_naver_html(
        self,
        content: str,
        title: str = "",
        keywords: Optional[List[str]] = None,
        emphasis_phrases: Optional[List[str]] = None,
    ) -> str:
        """
        네이버 블로그 전용 HTML 생성

        네이버 스마트에디터가 지원하는 태그만 사용:
        - <b>, <font color="">, <font size="">
        - <blockquote>, <ul>, <li>
        """
        html_parts = []

        # 제목
        if title:
            html_parts.append(f'<h2><b>{title}</b></h2>')
            html_parts.append('<br>')

        # 본문 처리
        paragraphs = content.split('\n\n')

        for para in paragraphs:
            if not para.strip():
                continue

            # 인용구
            if para.strip().startswith('>'):
                quote_text = para.replace('>', '').strip()
                html_parts.append(f'<blockquote>{quote_text}</blockquote>')

            # 제목
            elif para.strip().startswith('##'):
                heading = para.replace('#', '').strip()
                html_parts.append(f'<h3><b>{heading}</b></h3>')

            # 리스트
            elif para.strip().startswith(('- ', '* ')):
                items = para.split('\n')
                html_parts.append('<ul>')
                for item in items:
                    item_text = re.sub(r'^[\s\-\*]+', '', item).strip()
                    if item_text:
                        html_parts.append(f'<li>{item_text}</li>')
                html_parts.append('</ul>')

            # 일반 문단
            else:
                styled_text = self._apply_naver_styles(
                    para, keywords, emphasis_phrases
                )
                html_parts.append(f'<p>{styled_text}</p>')

        return '\n'.join(html_parts)

    def _apply_naver_styles(
        self,
        text: str,
        keywords: Optional[List[str]] = None,
        emphasis_phrases: Optional[List[str]] = None,
    ) -> str:
        """
        네이버 호환 스타일 적용
        """
        result = text

        # 키워드 강조 (빨간색 + 볼드)
        if keywords:
            for kw in sorted(keywords, key=len, reverse=True):
                pattern = re.compile(re.escape(kw), re.IGNORECASE)
                result = pattern.sub(
                    f'<b><font color="#FF6B6B">{kw}</font></b>',
                    result
                )

        # 강조 문구 (노란 배경)
        if emphasis_phrases:
            for phrase in sorted(emphasis_phrases, key=len, reverse=True):
                pattern = re.compile(re.escape(phrase), re.IGNORECASE)
                result = pattern.sub(
                    f'<span style="background-color: yellow;"><b>{phrase}</b></span>',
                    result
                )

        return result


# 싱글톤 인스턴스
blog_exporter = BlogExporter()
