from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Index
from datetime import datetime
from backend.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    # unique=True already creates a unique index on each of these — login
    # ("WHERE username = ?") and registration checks are index lookups already.
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class WaterQuality(Base):
    __tablename__ = "water_quality"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    influent_cod = Column(Float, nullable=False)
    flow_rate = Column(Float, nullable=False)
    water_temp = Column(Float, nullable=False)
    current_do = Column(Float, nullable=False)
    status = Column(String(50), default="Normal")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        # Covers: WHERE user_id = ? ORDER BY created_at DESC  (every user's
        # own history page/chart) — composite index, leftmost column = user_id.
        Index("idx_water_user_created", "user_id", "created_at"),
        # Covers: ORDER BY created_at DESC LIMIT 500 with no user_id filter
        # (the admin "all records" view) — the composite index above can't
        # serve this alone since user_id isn't filtered first.
        Index("idx_water_created", "created_at"),
    )

class AIPrediction(Base):
    __tablename__ = "ai_predictions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    influent_cod = Column(Float, nullable=False)
    flow_rate = Column(Float, nullable=False)
    water_temp = Column(Float, nullable=False)
    current_do = Column(Float, nullable=False)
    predicted_speed = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_pred_user_created", "user_id", "created_at"),
        Index("idx_pred_created", "created_at"),
    )
