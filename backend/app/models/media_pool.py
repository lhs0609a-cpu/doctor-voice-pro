"""
사진 풀 & 이미지 유니크화 모델
- 사진 40~50장을 미리 업로드(풀)해 두고, 글마다 자동 배정 + 유니크화
- 변형 pHash 로그로 "글 간 중복"까지 회피 (같은 원본 재사용 시 서로 다른 변형 보장)
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, ForeignKey, LargeBinary
)
from sqlalchemy.orm import relationship
from app.db.database import Base


class PoolImage(Base):
    """사용자가 미리 넣어둔 원본 사진 (풀)"""
    __tablename__ = "pool_images"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    filename = Column(String(255))
    content_type = Column(String(50), default="image/jpeg")
    data = Column(LargeBinary, nullable=False)          # 원본 바이트
    original_phash = Column(String(16), index=True)     # 원본 pHash(hex)
    width = Column(Integer)
    height = Column(Integer)
    size_bytes = Column(Integer)
    use_count = Column(Integer, default=0)              # 자동배정: 적게 쓴 것 우선
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)

    variants = relationship(
        "ImageVariant", back_populates="pool_image", cascade="all, delete-orphan"
    )


class PoolCollection(Base):
    """사진 목록(앨범). 예: '1목록' 에 사진 40장을 묶어두고 글마다 그 목록에서 배정."""
    __tablename__ = "pool_collections"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    members = relationship(
        "PoolCollectionMember", back_populates="collection", cascade="all, delete-orphan"
    )


class PoolCollectionMember(Base):
    """목록 ↔ 풀 사진 연결(한 사진이 여러 목록에 속할 수 있음)."""
    __tablename__ = "pool_collection_members"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    collection_id = Column(String(36), ForeignKey("pool_collections.id"), nullable=False, index=True)
    pool_image_id = Column(String(36), ForeignKey("pool_images.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    collection = relationship("PoolCollection", back_populates="members")


class ImageVariant(Base):
    """한 원본으로 생성한 유니크화 변형 이력 (해시만 보관, 바이트는 미보관)"""
    __tablename__ = "image_variants"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pool_image_id = Column(String(36), ForeignKey("pool_images.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    phash = Column(String(16), index=True)
    dhash = Column(String(16))
    frame_style = Column(String(30))
    ssim = Column(Float)
    min_distance = Column(Integer)      # 원본+형제 대비 최소 pHash 거리
    passed = Column(Boolean, default=False)
    post_id = Column(String(36), nullable=True)   # 삽입된 글(옵션)
    created_at = Column(DateTime, default=datetime.utcnow)

    pool_image = relationship("PoolImage", back_populates="variants")
