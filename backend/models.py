from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Text, ForeignKey, Boolean, Index
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
    # Which sold machine produced this reading (NULL for rows from before devices existed).
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True)
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
        # Covers: latest reading per machine (admin device list).
        Index("idx_water_device_created", "device_id", "created_at"),
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


class Device(Base):
    """A water-treatment machine that was sold. The dashboard is the bundled extra."""
    __tablename__ = "devices"
    id = Column(Integer, primary_key=True)
    serial_no = Column(String(100), unique=True, nullable=False)
    model_name = Column(String(100), nullable=False)
    # NULL = in stock / not yet assigned to a customer.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    purchased_at = Column(Date, nullable=False)
    warranty_until = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ServiceRequest(Base):
    """Customer repair / support ticket, handled from the admin dashboard."""
    __tablename__ = "service_requests"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True)
    subject = Column(String(150), nullable=False)
    detail = Column(Text, nullable=False)
    status = Column(String(20), default="open", nullable=False)  # open | in_progress | closed
    admin_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_sr_user_created", "user_id", "created_at"),
        Index("idx_sr_status", "status"),
    )
