"""Customer dashboard + admin dashboard endpoints for the machine-sales model.

Customer (any logged-in user)      Admin (is_admin)
  GET  /me/overview                  GET    /admin/overview
  GET  /service-requests             GET    /admin/devices
  POST /service-requests             POST   /admin/devices
                                     PATCH  /admin/devices/{id}
                                     DELETE /admin/devices/{id}
                                     GET    /admin/service-requests
                                     PATCH  /admin/service-requests/{id}
"""
import calendar
import os
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.auth import admin_from_token, user_from_token
from backend.database import get_db
from backend.models import Device, ServiceRequest, User, WaterQuality
from backend.rules import LABELS, evaluate
from backend.schemas import (
    DeviceCreate,
    DeviceUpdate,
    ServiceRequestCreate,
    ServiceRequestUpdate,
)

router = APIRouter()

OFFLINE_MINUTES = int(os.getenv("DEVICE_OFFLINE_MINUTES", "15"))
WARRANTY_SOON_DAYS = 30
LEVEL_RANK = {"ok": 0, "nodata": 1, "offline": 2, "warn": 3, "crit": 4}


def _iso(dt):
    # Stored as naive UTC; the trailing Z lets the browser convert to local time.
    return dt.isoformat() + "Z" if dt else None


def _add_months(d: date, months: int) -> date:
    year = d.year + (d.month - 1 + months) // 12
    month = (d.month - 1 + months) % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def _reading_dict(row):
    return {
        "influent_cod": row.influent_cod,
        "flow_rate": row.flow_rate,
        "water_temp": row.water_temp,
        "current_do": row.current_do,
        "created_at": _iso(row.created_at),
    }


def _device_state(last_row):
    """Level for a machine from its newest reading: ok / warn / crit / offline / nodata."""
    if last_row is None:
        return {"level": "nodata", "label": "ยังไม่มีข้อมูล", "issues": []}
    if datetime.utcnow() - last_row.created_at > timedelta(minutes=OFFLINE_MINUTES):
        return {"level": "offline", "label": "ไม่ส่งข้อมูล", "issues": []}
    return evaluate(last_row.current_do, last_row.influent_cod, last_row.water_temp)


def _latest_by_device(db: Session, device_ids):
    if not device_ids:
        return {}
    newest = (
        db.query(WaterQuality.device_id, func.max(WaterQuality.created_at).label("mx"))
        .filter(WaterQuality.device_id.in_(device_ids))
        .group_by(WaterQuality.device_id)
        .subquery()
    )
    rows = (
        db.query(WaterQuality)
        .join(
            newest,
            (WaterQuality.device_id == newest.c.device_id)
            & (WaterQuality.created_at == newest.c.mx),
        )
        .all()
    )
    return {r.device_id: r for r in rows}


def _warranty_info(device: Device):
    if not device.warranty_until:
        return {"warranty_until": None, "warranty_days_left": None}
    return {
        "warranty_until": device.warranty_until.isoformat(),
        "warranty_days_left": (device.warranty_until - date.today()).days,
    }


def _device_dict(device: Device, last_row, owner_name=None):
    state = _device_state(last_row)
    return {
        "id": device.id,
        "serial_no": device.serial_no,
        "model_name": device.model_name,
        "user_id": device.user_id,
        "owner": owner_name,
        "purchased_at": device.purchased_at.isoformat() if device.purchased_at else None,
        **_warranty_info(device),
        "level": state["level"],
        "label": state["label"],
        "last_seen": _iso(last_row.created_at) if last_row else None,
        "reading": _reading_dict(last_row) if last_row else None,
    }


def _admin_device_rows(db: Session):
    rows = (
        db.query(Device, User.username)
        .outerjoin(User, Device.user_id == User.id)
        .order_by(Device.id.desc())
        .all()
    )
    latest = _latest_by_device(db, [d.id for d, _ in rows])
    return [_device_dict(d, latest.get(d.id), owner) for d, owner in rows]


def _request_dict(sr: ServiceRequest, username=None, serial_no=None):
    return {
        "id": sr.id,
        "user_id": sr.user_id,
        "username": username,
        "device_id": sr.device_id,
        "serial_no": serial_no,
        "subject": sr.subject,
        "detail": sr.detail,
        "status": sr.status,
        "admin_note": sr.admin_note,
        "created_at": _iso(sr.created_at),
        "updated_at": _iso(sr.updated_at),
    }


# ---------------------------------------------------------------------------
# Customer dashboard
# ---------------------------------------------------------------------------

@router.get("/me/overview")
def my_overview(authorization: str = Header(default=""), db: Session = Depends(get_db)):
    user = user_from_token(authorization, db)

    devices = db.query(Device).filter(Device.user_id == user.id).order_by(Device.id).all()
    latest = _latest_by_device(db, [d.id for d in devices])

    newest = (
        db.query(WaterQuality)
        .filter(WaterQuality.user_id == user.id)
        .order_by(WaterQuality.created_at.desc())
        .first()
    )
    current = None
    if newest:
        ev = evaluate(newest.current_do, newest.influent_cod, newest.water_temp)
        current = {
            **_reading_dict(newest),
            "level": ev["level"],
            "label": ev["label"],
            "advice": ev["issues"] or ["ระบบทำงานปกติ ค่าทุกตัวอยู่ในเกณฑ์ ไม่ต้องดำเนินการใดเพิ่มเติม"],
        }

    since = datetime.utcnow() - timedelta(hours=24)
    count, avg_do, avg_cod, avg_temp, avg_flow = (
        db.query(
            func.count(WaterQuality.id),
            func.avg(WaterQuality.current_do),
            func.avg(WaterQuality.influent_cod),
            func.avg(WaterQuality.water_temp),
            func.avg(WaterQuality.flow_rate),
        )
        .filter(WaterQuality.user_id == user.id, WaterQuality.created_at >= since)
        .one()
    )
    normal = (
        db.query(func.count(WaterQuality.id))
        .filter(
            WaterQuality.user_id == user.id,
            WaterQuality.created_at >= since,
            WaterQuality.status == LABELS["ok"],
        )
        .scalar()
        or 0
    )

    open_requests = (
        db.query(func.count(ServiceRequest.id))
        .filter(ServiceRequest.user_id == user.id, ServiceRequest.status != "closed")
        .scalar()
        or 0
    )

    def r(v, n=2):
        return round(float(v), n) if v is not None else None

    return {
        "devices": [_device_dict(d, latest.get(d.id)) for d in devices],
        "current": current,
        "last_24h": {
            "readings": count,
            "avg_do": r(avg_do),
            "avg_cod": r(avg_cod, 1),
            "avg_temp": r(avg_temp, 1),
            "avg_flow": r(avg_flow, 1),
            "normal_percent": round(normal * 100 / count) if count else None,
        },
        "open_requests": open_requests,
    }


@router.get("/service-requests")
def my_service_requests(authorization: str = Header(default=""), db: Session = Depends(get_db)):
    user = user_from_token(authorization, db)
    rows = (
        db.query(ServiceRequest, Device.serial_no)
        .outerjoin(Device, ServiceRequest.device_id == Device.id)
        .filter(ServiceRequest.user_id == user.id)
        .order_by(ServiceRequest.created_at.desc())
        .limit(50)
        .all()
    )
    return [_request_dict(sr, user.username, serial) for sr, serial in rows]


@router.post("/service-requests")
def create_service_request(
    data: ServiceRequestCreate,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    user = user_from_token(authorization, db)

    if data.device_id is not None:
        owned = db.query(Device).filter(Device.id == data.device_id, Device.user_id == user.id).first()
        if not owned:
            raise HTTPException(400, "Device not found on your account")

    now = datetime.utcnow()
    sr = ServiceRequest(
        user_id=user.id,
        device_id=data.device_id,
        subject=data.subject.strip(),
        detail=data.detail.strip(),
        status="open",
        created_at=now,
        updated_at=now,
    )
    db.add(sr)
    db.commit()
    return {"message": "Service request sent", "id": sr.id}


# ---------------------------------------------------------------------------
# Admin dashboard
# ---------------------------------------------------------------------------

@router.get("/admin/overview")
def admin_overview(authorization: str = Header(default=""), db: Session = Depends(get_db)):
    admin_from_token(authorization, db)

    devices = _admin_device_rows(db)
    today = date.today()

    def warranty_soon(d):
        left = d["warranty_days_left"]
        return left is not None and 0 <= left <= WARRANTY_SOON_DAYS

    needs_attention = sorted(
        (d for d in devices if d["level"] in ("crit", "warn", "offline")),
        key=lambda d: -LEVEL_RANK[d["level"]],
    )

    since = datetime.utcnow() - timedelta(hours=24)
    return {
        "kpis": {
            "customers": db.query(func.count(User.id)).filter(User.is_admin == False).scalar() or 0,  # noqa: E712
            "devices_total": len(devices),
            "devices_unassigned": sum(1 for d in devices if d["user_id"] is None),
            "devices_critical": sum(1 for d in devices if d["level"] == "crit"),
            "devices_warning": sum(1 for d in devices if d["level"] == "warn"),
            "devices_offline": sum(1 for d in devices if d["level"] in ("offline", "nodata") and d["user_id"] is not None),
            "warranty_expiring_30d": sum(1 for d in devices if warranty_soon(d)),
            "warranty_expired": sum(1 for d in devices if d["warranty_days_left"] is not None and d["warranty_days_left"] < 0),
            "open_requests": db.query(func.count(ServiceRequest.id)).filter(ServiceRequest.status != "closed").scalar() or 0,
            "readings_24h": db.query(func.count(WaterQuality.id)).filter(WaterQuality.created_at >= since).scalar() or 0,
        },
        "attention": needs_attention[:8],
        "as_of": today.isoformat(),
    }


@router.get("/admin/devices")
def admin_list_devices(authorization: str = Header(default=""), db: Session = Depends(get_db)):
    admin_from_token(authorization, db)
    return _admin_device_rows(db)


@router.post("/admin/devices")
def admin_create_device(
    data: DeviceCreate,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    admin_from_token(authorization, db)

    serial = data.serial_no.strip()
    if db.query(Device).filter(Device.serial_no == serial).first():
        raise HTTPException(400, "Serial number already exists")
    if data.user_id is not None and not db.query(User).filter(User.id == data.user_id).first():
        raise HTTPException(404, "Customer not found")

    purchased = data.purchased_at or date.today()
    device = Device(
        serial_no=serial,
        model_name=data.model_name.strip(),
        user_id=data.user_id,
        purchased_at=purchased,
        warranty_until=_add_months(purchased, data.warranty_months),
    )
    db.add(device)
    db.commit()
    return {"message": "Device added", "id": device.id}


@router.patch("/admin/devices/{device_id}")
def admin_update_device(
    device_id: int,
    data: DeviceUpdate,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    admin_from_token(authorization, db)

    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(404, "Device not found")

    changes = data.model_dump(exclude_unset=True)
    if "user_id" in changes:
        if changes["user_id"] is not None and not db.query(User).filter(User.id == changes["user_id"]).first():
            raise HTTPException(404, "Customer not found")
        device.user_id = changes["user_id"]
    if "model_name" in changes and changes["model_name"]:
        device.model_name = changes["model_name"].strip()
    if "warranty_until" in changes:
        device.warranty_until = changes["warranty_until"]

    db.commit()
    return {"message": "Device updated"}


@router.delete("/admin/devices/{device_id}")
def admin_delete_device(
    device_id: int,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    admin_from_token(authorization, db)

    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(404, "Device not found")

    # Keep the history, just detach it from the removed machine.
    db.query(WaterQuality).filter(WaterQuality.device_id == device_id).update({"device_id": None})
    db.query(ServiceRequest).filter(ServiceRequest.device_id == device_id).update({"device_id": None})
    db.delete(device)
    db.commit()
    return {"message": "Device deleted"}


@router.get("/admin/service-requests")
def admin_list_service_requests(
    status: str = Query(default=""),
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    admin_from_token(authorization, db)

    q = (
        db.query(ServiceRequest, User.username, Device.serial_no)
        .join(User, ServiceRequest.user_id == User.id)
        .outerjoin(Device, ServiceRequest.device_id == Device.id)
    )
    if status in ("open", "in_progress", "closed"):
        q = q.filter(ServiceRequest.status == status)

    rows = q.order_by(ServiceRequest.created_at.desc()).limit(200).all()
    return [_request_dict(sr, username, serial) for sr, username, serial in rows]


@router.patch("/admin/service-requests/{request_id}")
def admin_update_service_request(
    request_id: int,
    data: ServiceRequestUpdate,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    admin_from_token(authorization, db)

    sr = db.query(ServiceRequest).filter(ServiceRequest.id == request_id).first()
    if not sr:
        raise HTTPException(404, "Request not found")

    changes = data.model_dump(exclude_unset=True)
    if changes.get("status"):
        sr.status = changes["status"]
    if "admin_note" in changes:
        sr.admin_note = (changes["admin_note"] or "").strip() or None
    sr.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Request updated", "status": sr.status}
