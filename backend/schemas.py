from datetime import date
from typing import Optional
from pydantic import BaseModel, EmailStr, Field

class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class WaterRequest(BaseModel):
    influent_cod: float
    flow_rate: float
    water_temp: float
    current_do: float

class PredictionRequest(BaseModel):
    influent_cod: float
    flow_rate: float
    water_temp: float
    current_do: float

class AdminRoleUpdate(BaseModel):
    is_admin: bool


class DeviceCreate(BaseModel):
    serial_no: str = Field(min_length=1, max_length=100)
    model_name: str = Field(min_length=1, max_length=100)
    user_id: Optional[int] = None
    purchased_at: Optional[date] = None
    warranty_months: int = Field(default=12, ge=0, le=120)

class DeviceUpdate(BaseModel):
    # Only fields actually sent are applied, so user_id=null means "unassign".
    model_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    user_id: Optional[int] = None
    warranty_until: Optional[date] = None

class ServiceRequestCreate(BaseModel):
    device_id: Optional[int] = None
    subject: str = Field(min_length=1, max_length=150)
    detail: str = Field(min_length=1, max_length=2000)

class ServiceRequestUpdate(BaseModel):
    status: Optional[str] = Field(default=None, pattern="^(open|in_progress|closed)$")
    admin_note: Optional[str] = Field(default=None, max_length=2000)
