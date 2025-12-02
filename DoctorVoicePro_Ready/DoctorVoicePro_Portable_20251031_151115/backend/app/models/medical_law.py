from sqlalchemy import Column, String, DateTime, Boolean, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
import enum

from app.db.database import Base


class ViolationSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MedicalLawRule(Base):
    __tablename__ = "medical_law_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Rule details
    category = Column(String(50), nullable=False)  # 절대적_표현, 비교_우위, etc.
    pattern = Column(Text, nullable=False)  # Regex pattern
    severity = Column(Enum(ViolationSeverity), default=ViolationSeverity.MEDIUM)
    alternative_suggestion = Column(Text, nullable=True)

    # Status
    is_active = Column(Boolean, default=True)

    # Description
    description = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
