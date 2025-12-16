"""Check user in database"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.models.user import User
from app.core.config import settings
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

sync_db_url = settings.DATABASE_URL_SYNC
engine = create_engine(sync_db_url)

with Session(engine) as session:
    users = session.query(User).all()
    print(f"Total users: {len(users)}")
    for user in users:
        print(f"\nEmail: {user.email}")
        print(f"Name: {user.name}")
        print(f"is_active: {user.is_active}")
        print(f"is_verified: {user.is_verified}")
        print(f"is_approved: {user.is_approved}")
        print(f"is_admin: {user.is_admin}")
        print(f"subscription_tier: {user.subscription_tier}")
        print(f"subscription_start_date: {user.subscription_start_date}")
        print(f"subscription_end_date: {user.subscription_end_date}")
        print(f"Hashed password starts with: {user.hashed_password[:20]}...")

        # Test password verification
        test_password = "admin123!@#"
        is_valid = pwd_context.verify(test_password, user.hashed_password)
        print(f"Password 'admin123!@#' is valid: {is_valid}")

engine.dispose()
