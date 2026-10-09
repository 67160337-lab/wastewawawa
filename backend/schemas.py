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


class ProductCreate(BaseModel):
    model_code: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=150)
    description: Optional[str] = Field(default=None, max_length=2000)
    max_flow_m3h: Optional[float] = Field(default=None, ge=0)
    airflow_m3min: Optional[float] = Field(default=None, ge=0)
    power_kw: Optional[float] = Field(default=None, ge=0)
    price: float = Field(ge=0)
    stock: int = Field(default=0, ge=0)
    warranty_months: int = Field(default=12, ge=0, le=120)
    active: bool = True

class ProductUpdate(BaseModel):
    model_code: Optional[str] = Field(default=None, min_length=1, max_length=60)
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    description: Optional[str] = Field(default=None, max_length=2000)
    max_flow_m3h: Optional[float] = Field(default=None, ge=0)
    airflow_m3min: Optional[float] = Field(default=None, ge=0)
    power_kw: Optional[float] = Field(default=None, ge=0)
    price: Optional[float] = Field(default=None, ge=0)
    stock: Optional[int] = Field(default=None, ge=0)
    warranty_months: Optional[int] = Field(default=None, ge=0, le=120)
    active: Optional[bool] = None

class OrderItemIn(BaseModel):
    product_id: int
    quantity: int = Field(ge=1, le=100)

class OrderCreate(BaseModel):
    items: list[OrderItemIn] = Field(min_length=1, max_length=20)
    contact_phone: str = Field(min_length=5, max_length=30)
    shipping_address: str = Field(min_length=1, max_length=500)
    note: Optional[str] = Field(default=None, max_length=500)

class OrderUpdate(BaseModel):
    status: str = Field(pattern="^(pending|confirmed|shipped|completed|cancelled)$")
