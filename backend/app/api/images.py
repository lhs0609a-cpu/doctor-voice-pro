"""
Images API Router
imgBB를 통한 이미지 업로드
"""

import os
import base64
import httpx
from typing import List
from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel

router = APIRouter()

# imgBB API 키 (환경변수에서 가져오기)
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY", "")
IMGBB_UPLOAD_URL = "https://api.imgbb.com/1/upload"


class ImageUploadResponse(BaseModel):
    success: bool
    url: str
    delete_url: str | None = None
    thumbnail: str | None = None


class Base64ImageRequest(BaseModel):
    image: str  # base64 encoded image
    name: str | None = None


class MultiImageUploadResponse(BaseModel):
    success: bool
    images: List[ImageUploadResponse]
    failed: int = 0


@router.post("/upload", response_model=ImageUploadResponse)
async def upload_image(file: UploadFile = File(...)):
    """
    이미지 파일을 imgBB에 업로드

    - 지원 형식: JPG, PNG, GIF, WEBP
    - 최대 크기: 32MB
    """
    if not IMGBB_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="imgBB API 키가 설정되지 않았습니다"
        )

    # 파일 읽기 및 base64 인코딩
    content = await file.read()
    base64_image = base64.b64encode(content).decode('utf-8')

    # imgBB API 호출
    async with httpx.AsyncClient() as client:
        response = await client.post(
            IMGBB_UPLOAD_URL,
            data={
                "key": IMGBB_API_KEY,
                "image": base64_image,
                "name": file.filename or "image"
            },
            timeout=30.0
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"imgBB 업로드 실패: {response.text}"
        )

    result = response.json()

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"imgBB 업로드 실패: {result.get('error', {}).get('message', 'Unknown error')}"
        )

    data = result["data"]

    return ImageUploadResponse(
        success=True,
        url=data["url"],
        delete_url=data.get("delete_url"),
        thumbnail=data.get("thumb", {}).get("url")
    )


@router.post("/upload-base64", response_model=ImageUploadResponse)
async def upload_base64_image(request: Base64ImageRequest):
    """
    Base64 인코딩된 이미지를 imgBB에 업로드

    - image: base64 문자열 (data:image/png;base64,... 형식 또는 순수 base64)
    - name: 파일명 (선택)
    """
    if not IMGBB_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="imgBB API 키가 설정되지 않았습니다"
        )

    # data:image/xxx;base64, 접두사 제거
    image_data = request.image
    if "," in image_data:
        image_data = image_data.split(",")[1]

    # imgBB API 호출
    async with httpx.AsyncClient() as client:
        response = await client.post(
            IMGBB_UPLOAD_URL,
            data={
                "key": IMGBB_API_KEY,
                "image": image_data,
                "name": request.name or "image"
            },
            timeout=30.0
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"imgBB 업로드 실패: {response.text}"
        )

    result = response.json()

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"imgBB 업로드 실패: {result.get('error', {}).get('message', 'Unknown error')}"
        )

    data = result["data"]

    return ImageUploadResponse(
        success=True,
        url=data["url"],
        delete_url=data.get("delete_url"),
        thumbnail=data.get("thumb", {}).get("url")
    )


@router.post("/upload-multiple", response_model=MultiImageUploadResponse)
async def upload_multiple_images(files: List[UploadFile] = File(...)):
    """
    여러 이미지를 한 번에 업로드

    - 최대 10개까지 동시 업로드
    """
    if not IMGBB_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="imgBB API 키가 설정되지 않았습니다"
        )

    if len(files) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="최대 10개까지 업로드 가능합니다"
        )

    results = []
    failed = 0

    async with httpx.AsyncClient() as client:
        for file in files:
            try:
                content = await file.read()
                base64_image = base64.b64encode(content).decode('utf-8')

                response = await client.post(
                    IMGBB_UPLOAD_URL,
                    data={
                        "key": IMGBB_API_KEY,
                        "image": base64_image,
                        "name": file.filename or "image"
                    },
                    timeout=30.0
                )

                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        data = result["data"]
                        results.append(ImageUploadResponse(
                            success=True,
                            url=data["url"],
                            delete_url=data.get("delete_url"),
                            thumbnail=data.get("thumb", {}).get("url")
                        ))
                        continue

                failed += 1
            except Exception as e:
                print(f"Image upload failed: {e}")
                failed += 1

    return MultiImageUploadResponse(
        success=len(results) > 0,
        images=results,
        failed=failed
    )


@router.get("/status")
async def get_imgbb_status():
    """
    imgBB API 연결 상태 확인
    """
    return {
        "configured": bool(IMGBB_API_KEY),
        "api_key_preview": f"{IMGBB_API_KEY[:8]}..." if IMGBB_API_KEY else None
    }
