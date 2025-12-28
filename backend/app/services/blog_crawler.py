"""
Blog Crawler Service
블로그 글 크롤링 서비스 - 네이버 블로그, 티스토리 등 지원
"""

import re
import httpx
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, parse_qs, urljoin
import json


class BlogCrawler:
    """블로그 글 크롤링 서비스"""

    # 공통 헤더
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    async def crawl(self, url: str, include_images: bool = True) -> Dict[str, Any]:
        """
        블로그 URL에서 글 내용을 추출합니다.

        Args:
            url: 블로그 글 URL
            include_images: 이미지도 함께 추출할지 여부

        Returns:
            {
                "success": bool,
                "title": str,
                "content": str,
                "platform": str,  # "naver", "tistory", "other"
                "author": str (optional),
                "date": str (optional),
                "images": list (optional),  # 이미지 URL 목록
                "error": str (optional)
            }
        """
        try:
            # URL 정규화
            url = url.strip()
            if not url.startswith(("http://", "https://")):
                url = "https://" + url

            # 플랫폼 감지
            platform = self._detect_platform(url)

            # 플랫폼별 크롤링
            if platform == "naver":
                return await self._crawl_naver_blog(url)
            elif platform == "tistory":
                return await self._crawl_tistory(url)
            else:
                return await self._crawl_generic(url)

        except httpx.TimeoutException:
            return {
                "success": False,
                "error": "요청 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.",
                "platform": "unknown"
            }
        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "error": f"페이지를 불러올 수 없습니다. (HTTP {e.response.status_code})",
                "platform": "unknown"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"크롤링 중 오류가 발생했습니다: {str(e)}",
                "platform": "unknown"
            }

    def _detect_platform(self, url: str) -> str:
        """URL에서 블로그 플랫폼을 감지합니다."""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        if "blog.naver.com" in domain or "m.blog.naver.com" in domain:
            return "naver"
        elif "tistory.com" in domain:
            return "tistory"
        elif "brunch.co.kr" in domain:
            return "brunch"
        elif "velog.io" in domain:
            return "velog"
        else:
            return "other"

    async def _crawl_naver_blog(self, url: str) -> Dict[str, Any]:
        """네이버 블로그 크롤링"""

        # 모바일 URL로 변환 (크롤링 용이)
        mobile_url = self._convert_to_mobile_naver(url)

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(mobile_url, headers=self.HEADERS)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        # 제목 추출
        title = ""
        title_elem = soup.select_one(".se-title-text, .tit_h3, .__se_title, .pcol1")
        if title_elem:
            title = title_elem.get_text(strip=True)

        # 본문 추출 (스마트에디터 3.0 / 2.0)
        content = ""

        # 스마트에디터 3.0 (SE3)
        content_elem = soup.select_one(".se-main-container")
        if content_elem:
            content = self._extract_naver_se3_content(content_elem)
        else:
            # 스마트에디터 2.0
            content_elem = soup.select_one("#postViewArea, .post-view, .__se_component_area")
            if content_elem:
                content = self._extract_text_with_newlines(content_elem)

        # iframe 내부 콘텐츠 확인 (구버전 블로그)
        if not content:
            iframe = soup.select_one("iframe#mainFrame")
            if iframe:
                iframe_src = iframe.get("src", "")
                if iframe_src:
                    if not iframe_src.startswith("http"):
                        iframe_src = "https://blog.naver.com" + iframe_src
                    return await self._crawl_naver_iframe(iframe_src)

        if not content:
            return {
                "success": False,
                "error": "블로그 본문을 찾을 수 없습니다. URL을 확인해주세요.",
                "platform": "naver"
            }

        # 이미지 추출
        images = []
        if content_elem:
            images = self._extract_naver_images(content_elem, url)

        # 작성자, 날짜 추출
        author = ""
        author_elem = soup.select_one(".nick, .blog_author")
        if author_elem:
            author = author_elem.get_text(strip=True)

        date = ""
        date_elem = soup.select_one(".se_publishDate, .date")
        if date_elem:
            date = date_elem.get_text(strip=True)

        return {
            "success": True,
            "title": title,
            "content": content,
            "platform": "naver",
            "author": author,
            "date": date,
            "images": images,
            "url": url
        }

    async def _crawl_naver_iframe(self, iframe_url: str) -> Dict[str, Any]:
        """네이버 블로그 iframe 내부 크롤링 (구버전)"""
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(iframe_url, headers=self.HEADERS)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        title = ""
        title_elem = soup.select_one(".pcol1, .se-title-text, .__se_title")
        if title_elem:
            title = title_elem.get_text(strip=True)

        content = ""
        content_elem = soup.select_one("#postViewArea, .se-main-container")
        if content_elem:
            content = self._extract_text_with_newlines(content_elem)

        if not content:
            return {
                "success": False,
                "error": "블로그 본문을 찾을 수 없습니다.",
                "platform": "naver"
            }

        # 이미지 추출
        images = []
        if content_elem:
            images = self._extract_naver_images(content_elem, iframe_url)

        return {
            "success": True,
            "title": title,
            "content": content,
            "platform": "naver",
            "author": "",
            "date": "",
            "images": images
        }

    def _convert_to_mobile_naver(self, url: str) -> str:
        """네이버 블로그 URL을 모바일 버전으로 변환"""
        # blog.naver.com/blogId/postId 형식
        parsed = urlparse(url)

        if "m.blog.naver.com" in parsed.netloc:
            return url  # 이미 모바일

        # PC URL을 모바일로 변환
        return url.replace("blog.naver.com", "m.blog.naver.com")

    def _extract_naver_se3_content(self, container) -> str:
        """네이버 스마트에디터 3.0 본문 추출"""
        paragraphs = []

        # 텍스트 컴포넌트
        for component in container.select(".se-component"):
            # 텍스트
            text_elem = component.select_one(".se-text-paragraph")
            if text_elem:
                text = text_elem.get_text(strip=True)
                if text:
                    paragraphs.append(text)
                continue

            # 인용구
            quote_elem = component.select_one(".se-quotation-content")
            if quote_elem:
                quote_text = quote_elem.get_text(strip=True)
                if quote_text:
                    paragraphs.append(f"> {quote_text}")
                continue

            # 제목/헤더
            header_elem = component.select_one(".se-section-title .se-text-paragraph")
            if header_elem:
                header_text = header_elem.get_text(strip=True)
                if header_text:
                    paragraphs.append(f"\n## {header_text}\n")
                continue

        return "\n\n".join(paragraphs)

    async def _crawl_tistory(self, url: str) -> Dict[str, Any]:
        """티스토리 블로그 크롤링"""
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url, headers=self.HEADERS)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        # 제목 추출
        title = ""
        title_selectors = [
            ".entry-title", ".title_post", ".article-header h1",
            ".tit_post", "h1.title", ".post-header h1", "article h1"
        ]
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                title = title_elem.get_text(strip=True)
                break

        # 본문 추출
        content = ""
        content_selectors = [
            ".entry-content", ".article-content", ".post-content",
            ".tt_article_useless_p_margin", ".contents_style",
            "#article-view", ".area_view", "article .content"
        ]
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                content = self._extract_text_with_newlines(content_elem)
                break

        if not content:
            return {
                "success": False,
                "error": "블로그 본문을 찾을 수 없습니다. URL을 확인해주세요.",
                "platform": "tistory"
            }

        # 이미지 추출
        images = []
        if content_elem:
            images = self._extract_images(content_elem, url, "tistory")

        # 작성자, 날짜
        author = ""
        author_elem = soup.select_one(".author, .writer")
        if author_elem:
            author = author_elem.get_text(strip=True)

        date = ""
        date_elem = soup.select_one(".date, time, .post-date")
        if date_elem:
            date = date_elem.get_text(strip=True)

        return {
            "success": True,
            "title": title,
            "content": content,
            "platform": "tistory",
            "author": author,
            "date": date,
            "images": images,
            "url": url
        }

    async def _crawl_generic(self, url: str) -> Dict[str, Any]:
        """일반 웹페이지 크롤링"""
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url, headers=self.HEADERS)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        # 제목 추출
        title = ""
        title_elem = soup.select_one("h1, .title, .post-title, article h1")
        if title_elem:
            title = title_elem.get_text(strip=True)
        elif soup.title:
            title = soup.title.get_text(strip=True)

        # 본문 추출 (article, main, content 우선)
        content = ""
        content_selectors = [
            "article", "main", ".content", ".post-content",
            ".article-content", ".entry-content", "#content"
        ]
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                content = self._extract_text_with_newlines(content_elem)
                if len(content) > 100:  # 충분한 내용이 있으면 사용
                    break

        if not content:
            # body 전체에서 추출 시도
            body = soup.find("body")
            if body:
                # 불필요한 요소 제거
                for tag in body.select("script, style, nav, header, footer, aside"):
                    tag.decompose()
                content = self._extract_text_with_newlines(body)

        if not content or len(content) < 50:
            return {
                "success": False,
                "error": "페이지에서 본문을 추출할 수 없습니다.",
                "platform": "other"
            }

        # 이미지 추출
        images = []
        if content_elem:
            images = self._extract_images(content_elem, url, "other")

        return {
            "success": True,
            "title": title,
            "content": content,
            "platform": "other",
            "author": "",
            "date": "",
            "images": images,
            "url": url
        }

    def _extract_text_with_newlines(self, element) -> str:
        """HTML 요소에서 텍스트를 줄바꿈을 유지하며 추출"""
        # 불필요한 요소 제거
        for tag in element.select("script, style, nav, .ad, .advertisement"):
            tag.decompose()

        # 블록 요소 앞뒤로 줄바꿈 추가
        for tag in element.find_all(["p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li"]):
            if tag.name == "br":
                tag.replace_with("\n")
            else:
                tag.insert_before("\n")
                tag.insert_after("\n")

        # 텍스트 추출
        text = element.get_text()

        # 정리
        lines = []
        for line in text.split("\n"):
            line = line.strip()
            if line:
                lines.append(line)

        # 연속 빈 줄 제거
        result = "\n\n".join(lines)

        # 과도한 공백 정리
        result = re.sub(r'\n{3,}', '\n\n', result)

        return result.strip()

    def _extract_images(self, element, base_url: str, platform: str = "other") -> List[Dict[str, Any]]:
        """HTML 요소에서 이미지를 추출합니다."""
        images = []
        seen_urls = set()

        # 이미지 태그 찾기
        img_tags = element.select("img")

        for img in img_tags:
            # 이미지 URL 추출 (다양한 속성 확인)
            img_url = None

            # 네이버 블로그는 data-lazy-src 또는 data-src 사용
            if platform == "naver":
                img_url = (
                    img.get("data-lazy-src") or
                    img.get("data-src") or
                    img.get("src")
                )
            else:
                img_url = (
                    img.get("data-src") or
                    img.get("data-lazy-src") or
                    img.get("data-original") or
                    img.get("src")
                )

            if not img_url:
                continue

            # 상대 URL을 절대 URL로 변환
            if img_url.startswith("//"):
                img_url = "https:" + img_url
            elif img_url.startswith("/"):
                img_url = urljoin(base_url, img_url)
            elif not img_url.startswith("http"):
                img_url = urljoin(base_url, img_url)

            # 작은 이미지, 아이콘, 이모티콘 등 필터링
            if self._is_valid_content_image(img_url, img):
                # 중복 제거
                if img_url not in seen_urls:
                    seen_urls.add(img_url)

                    # 이미지 정보 추출
                    alt_text = img.get("alt", "")
                    width = img.get("width", "")
                    height = img.get("height", "")

                    images.append({
                        "url": img_url,
                        "alt": alt_text,
                        "width": width,
                        "height": height,
                    })

        return images

    def _is_valid_content_image(self, url: str, img_tag) -> bool:
        """콘텐츠 이미지인지 확인 (아이콘, 이모티콘 등 제외)"""
        url_lower = url.lower()

        # 제외할 패턴
        exclude_patterns = [
            "icon", "logo", "button", "btn",
            "emoji", "emoticon", "sticker",
            "loading", "spinner", "placeholder",
            "blank.gif", "spacer.gif", "1x1",
            "avatar", "profile", "badge",
            "ad.", "ads.", "banner",
            "static.naver.net",  # 네이버 기본 아이콘
            "blogpfthumb",  # 네이버 프로필 썸네일
            "se-symbol",  # 네이버 기호
            ".svg",  # SVG 아이콘
        ]

        for pattern in exclude_patterns:
            if pattern in url_lower:
                return False

        # 크기로 필터링 (있는 경우)
        try:
            width = int(img_tag.get("width", 0))
            height = int(img_tag.get("height", 0))
            if width > 0 and height > 0:
                # 너무 작은 이미지 제외 (100x100 미만)
                if width < 100 and height < 100:
                    return False
        except (ValueError, TypeError):
            pass

        # 네이버 블로그 실제 이미지 URL 패턴 확인
        if "blogfiles" in url_lower or "pstatic.net" in url_lower:
            # 네이버 블로그 이미지
            return True

        # 티스토리 이미지 패턴
        if "tistory" in url_lower and ("cfile" in url_lower or "img" in url_lower):
            return True

        # 일반적인 이미지 확장자 확인
        image_extensions = [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"]
        for ext in image_extensions:
            if ext in url_lower:
                return True

        return True  # 기본적으로 허용

    def _extract_naver_images(self, container, base_url: str) -> List[Dict[str, Any]]:
        """네이버 블로그 이미지 추출 (스마트에디터 최적화)"""
        images = []
        seen_urls = set()

        # SE3 이미지 모듈
        for img_module in container.select(".se-image, .se-imageStrip"):
            img = img_module.select_one("img")
            if img:
                # 네이버는 data-lazy-src에 원본 이미지 URL
                img_url = (
                    img.get("data-lazy-src") or
                    img.get("data-src") or
                    img.get("src")
                )

                if img_url and img_url not in seen_urls:
                    # 썸네일을 원본으로 변환
                    img_url = self._convert_naver_image_to_original(img_url)
                    seen_urls.add(img_url)

                    # 캡션 추출
                    caption = ""
                    caption_elem = img_module.select_one(".se-caption, .se-text-paragraph")
                    if caption_elem:
                        caption = caption_elem.get_text(strip=True)

                    images.append({
                        "url": img_url,
                        "alt": img.get("alt", ""),
                        "caption": caption,
                    })

        # 일반 이미지도 추출
        if not images:
            images = self._extract_images(container, base_url, "naver")

        return images

    def _convert_naver_image_to_original(self, url: str) -> str:
        """네이버 이미지 URL을 원본 크기로 변환"""
        # 썸네일 파라미터 제거
        if "?" in url:
            base = url.split("?")[0]
            # 원본 요청 파라미터 추가
            return base + "?type=w966"
        return url


# 싱글톤 인스턴스
blog_crawler = BlogCrawler()
