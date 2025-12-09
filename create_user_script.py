from app.database import SessionLocal
from app.models.user import User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
db = SessionLocal()

# Check if user exists
existing = db.query(User).filter(User.email == "test@example.com").first()
if existing:
    print("User already exists")
else:
    user = User(
        email="test@example.com",
        hashed_password=pwd_context.hash("password123"),
        is_active=True,
        is_admin=True,
        name="Test User"
    )
    db.add(user)
    db.commit()
    print("User created successfully")

db.close()
