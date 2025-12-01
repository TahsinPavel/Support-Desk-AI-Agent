from database import SessionLocal
from models import User, Channel
import uuid

db = SessionLocal()

user = db.query(User).filter(User.email=="owner@example.com").first()

if not user:
    # Create new user
    user = User(
        business_name="Demo Business",
        email="owner@example.com",
        phone_number="0000000000",
        plan="Starter",
        ai_provider="gemini"  # or"openai"
    )
    db.add(user)
else:
    # Update AI provider or other fields
    user.ai_provider = "gemini"

db.commit()
db.refresh(user)

# Create email channel
channel = Channel(
    user_id=user.id,
    type="email",
    identifier="support@example.com"
)
db.add(channel)
db.commit()

print("User + Channel created!")




