"""
Keyword Prompt Template Model
키워드 대량 생성 - 프롬프트 템플릿 (계정별 서버 저장)

기존에는 브라우저 localStorage 에만 있어 다른 컴퓨터에서 안 보였다.
계정에 묶어 저장해 어느 기기에서 로그인하든 같은 템플릿을 쓰게 한다.
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from datetime import datetime
import uuid as uuid_pkg

from app.db.database import Base
from app.models.user import GUID


class KeywordPromptTemplate(Base):
    __tablename__ = "keyword_prompt_templates"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)

    # 프론트가 만든 식별자(default, tpl-...). 화면의 선택 상태(activeId) 매칭용으로 보존한다.
    client_id = Column(String(64), nullable=False)
    name = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)

    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<KeywordPromptTemplate {self.name}>"
