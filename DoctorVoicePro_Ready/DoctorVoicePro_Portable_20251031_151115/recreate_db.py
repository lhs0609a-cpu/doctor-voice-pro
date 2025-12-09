"""
Database recreation script
Recreates all tables with the latest schema and creates default admin user
"""
import asyncio
import sys
from pathlib import Path

# Add the parent directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from backend.app.db.database import Base
from backend.app.models.user import User
from backend.app.models.post import Post, PostVersion, PostAnalytics
from backend.app.models.doctor_profile import DoctorProfile
from backend.app.models.tag import Tag
from backend.app.models.naver_connection import NaverConnection
from backend.app.models.medical_law import MedicalLawRule
from backend.app.core.config import settings
from passlib.context import CryptContext
import uuid

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def recreate_database():
    """Recreate all database tables"""
    print("Recreating database...")

    # Use sync engine for table creation
    sync_db_url = settings.DATABASE_URL_SYNC
    engine = create_engine(sync_db_url, echo=False)

    # Drop all tables
    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)

    # Create all tables
    print("Creating all tables...")
    Base.metadata.create_all(bind=engine)

    print("Database tables created successfully!")

    # Create default admin user
    print("Creating default admin user...")
    with Session(engine) as session:
        admin_user = User(
            id=uuid.uuid4(),
            email="admin@doctorvoice.com",
            hashed_password=pwd_context.hash("admin123!@#"),
            name="관리자",
            hospital_name="닥터보이스 프로",
            specialty="일반의",
            subscription_tier="PRO",
            is_active=True,
            is_verified=True,
            is_approved=True,
            is_admin=True,
        )
        session.add(admin_user)
        session.commit()
        print(f"Admin user created: {admin_user.email}")
        print(f"Password: admin123!@#")

    engine.dispose()
    print("\nDatabase recreation completed!")


if __name__ == "__main__":
    recreate_database()
