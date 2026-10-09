"""Product catalogue + orders (no online payment: the seller confirms each order)."""
import os
import calendar
from datetime import date, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from backend.auth import admin_from_token, user_from_token
from backend.database import SessionLocal, get_db
from backend.models import Device, Order, OrderItem, Product, User
from backend.schemas import OrderCreate, OrderUpdate, ProductCreate, ProductUpdate

router = APIRouter()


def _iso(dt):
    return dt.isoformat() + "Z" if dt else None


def _product_dict(p: Product):
    return {
        "id": p.id,
        "model_code": p.model_code,
        "name": p.name,
        "description": p.description,
        "max_flow_m3h": p.max_flow_m3h,
        "airflow_m3min": p.airflow_m3min,
        "power_kw": p.power_kw,
        "price": p.price,
        "stock": p.stock,
        "warranty_months": p.warranty_months,
        "active": p.active,
    }


def _orders_payload(db: Session, orders, usernames=None):
    ids = [o.id for o in orders]
    items = db.query(OrderItem).filter(OrderItem.order_id.in_(ids)).all() if ids else []
    by_order = {}
    for it in items:
        by_order.setdefault(it.order_id, []).append({
            "product_id": it.product_id,
            "product_name": it.product_name,
            "unit_price": it.unit_price,
            "quantity": it.quantity,
        })
    return [{
        "id": o.id,
        "username": (usernames or {}).get(o.user_id),
        "status": o.status,
        "total": o.total,
        "contact_phone": o.contact_phone,
        "shipping_address": o.shipping_address,
        "note": o.note,
        "items": by_order.get(o.id, []),
        "created_at": _iso(o.created_at),
        "updated_at": _iso(o.updated_at),
    } for o in orders]


def _restock(db: Session, order_id: int):
    for it in db.query(OrderItem).filter(OrderItem.order_id == order_id).all():
        if it.product_id is not None:
            db.query(Product).filter(Product.id == it.product_id).update(
                {Product.stock: Product.stock + it.quantity}
            )


# Starter catalogue. Specs and prices are starting values for you to edit in
# the admin dashboard (Admin > สินค้า), so check them against your real products.
STARTER_PRODUCTS = [
    dict(model_code="AB-15", name="AeroBlow AB-15 เครื่องเติมอากาศขนาดเล็ก",
         description="Ring blower 1.5 kW เหมาะกับระบบบำบัดน้ำเสียขนาดเล็ก เช่น หอพัก ร้านอาหาร อาคารขนาดเล็ก เสียงเงียบ ไม่ต้องใช้น้ำมันหล่อลื่น",
         max_flow_m3h=40, airflow_m3min=2.0, power_kw=1.5, price=28900, stock=10, warranty_months=12),
    dict(model_code="AB-22", name="AeroBlow AB-22 เครื่องเติมอากาศขนาดกลาง",
         description="Ring blower 2.2 kW เหมาะกับโรงแรมขนาดเล็ก โรงงานขนาดเล็ก หรือชุมชน รองรับน้ำเสียที่มีค่า COD ปานกลาง",
         max_flow_m3h=60, airflow_m3min=3.0, power_kw=2.2, price=36500, stock=8, warranty_months=12),
    dict(model_code="AB-37", name="AeroBlow AB-37 เครื่องเติมอากาศขนาดกลาง-ใหญ่",
         description="Ring blower 3.7 kW เหมาะกับโรงงานอาหาร ฟาร์ม หรืออาคารขนาดใหญ่ ที่มีปริมาณน้ำเสียต่อชั่วโมงสูง",
         max_flow_m3h=100, airflow_m3min=5.0, power_kw=3.7, price=54900, stock=5, warranty_months=18),
    dict(model_code="AB-55", name="AeroBlow AB-55 เครื่องเติมอากาศขนาดใหญ่",
         description="Ring blower 5.5 kW สำหรับระบบบำบัดขนาดใหญ่ ทำงานต่อเนื่อง 24 ชั่วโมง ควบคุมความเร็วจาก AI ได้เต็มประสิทธิภาพ",
         max_flow_m3h=150, airflow_m3min=7.5, power_kw=5.5, price=79000, stock=3, warranty_months=24),
]


def seed_starter_products():
    """Fill an EMPTY catalogue with the starter products above.
    Set SEED_PRODUCTS=false to disable. Never touches a catalogue that already has products."""
    if os.getenv("SEED_PRODUCTS", "true").lower() == "false":
        return
    db = SessionLocal()
    try:
        if db.query(Product).count():
            return
        for item in STARTER_PRODUCTS:
            db.add(Product(**item))
        db.commit()
        print(f"Seeded {len(STARTER_PRODUCTS)} starter products.")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------

@router.get("/products")
def list_products(authorization: str = Header(default=""), db: Session = Depends(get_db)):
    user_from_token(authorization, db)
    rows = db.query(Product).filter(Product.active == True).order_by(Product.price.asc()).all()  # noqa: E712
    return [_product_dict(p) for p in rows]


@router.post("/orders")
def create_order(data: OrderCreate, authorization: str = Header(default=""), db: Session = Depends(get_db)):
    user = user_from_token(authorization, db)

    wanted = {}
    for it in data.items:  # merge duplicate lines
        wanted[it.product_id] = wanted.get(it.product_id, 0) + it.quantity

    products = {p.id: p for p in db.query(Product).filter(Product.id.in_(list(wanted))).all()}
    for pid in wanted:
        p = products.get(pid)
        if not p or not p.active:
            raise HTTPException(400, "Product is not available")

    total = 0.0
    try:
        for pid, qty in wanted.items():
            # Conditional UPDATE: stock can never go negative even with two buyers at once.
            changed = (
                db.query(Product)
                .filter(Product.id == pid, Product.stock >= qty)
                .update({Product.stock: Product.stock - qty})
            )
            if not changed:
                raise HTTPException(400, f"สินค้า {products[pid].name} มีไม่พอ (เหลือไม่ถึง {qty} เครื่อง)")
            total += products[pid].price * qty

        now = datetime.utcnow()
        order = Order(
            user_id=user.id,
            status="pending",
            total=round(total, 2),
            contact_phone=data.contact_phone.strip(),
            shipping_address=data.shipping_address.strip(),
            note=(data.note or "").strip() or None,
            created_at=now,
            updated_at=now,
        )
        db.add(order)
        db.flush()
        for pid, qty in wanted.items():
            db.add(OrderItem(order_id=order.id, product_id=pid, product_name=products[pid].name,
                             unit_price=products[pid].price, quantity=qty))
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    return {"message": "Order placed", "id": order.id, "total": order.total}


@router.get("/orders")
def my_orders(authorization: str = Header(default=""), db: Session = Depends(get_db)):
    user = user_from_token(authorization, db)
    orders = (
        db.query(Order).filter(Order.user_id == user.id)
        .order_by(Order.created_at.desc()).limit(50).all()
    )
    return _orders_payload(db, orders, {user.id: user.username})


@router.post("/orders/{order_id}/cancel")
def cancel_my_order(order_id: int, authorization: str = Header(default=""), db: Session = Depends(get_db)):
    user = user_from_token(authorization, db)
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == user.id).first()
    if not order:
        raise HTTPException(404, "Order not found")
    if order.status != "pending":
        raise HTTPException(400, "ยกเลิกเองได้เฉพาะคำสั่งซื้อที่ยังรอการยืนยัน กรุณาติดต่อทีมงาน")
    order.status = "cancelled"
    order.updated_at = datetime.utcnow()
    _restock(db, order.id)
    db.commit()
    return {"message": "Order cancelled"}


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

@router.get("/admin/products")
def admin_products(authorization: str = Header(default=""), db: Session = Depends(get_db)):
    admin_from_token(authorization, db)
    return [_product_dict(p) for p in db.query(Product).order_by(Product.id.desc()).all()]


@router.post("/admin/products")
def admin_create_product(data: ProductCreate, authorization: str = Header(default=""), db: Session = Depends(get_db)):
    admin_from_token(authorization, db)
    code = data.model_code.strip()
    if db.query(Product).filter(Product.model_code == code).first():
        raise HTTPException(400, "Model code already exists")
    fields = data.model_dump()
    fields["model_code"] = code
    fields["name"] = data.name.strip()
    p = Product(**fields)
    db.add(p)
    db.commit()
    return {"message": "Product added", "id": p.id}


@router.patch("/admin/products/{product_id}")
def admin_update_product(product_id: int, data: ProductUpdate,
                         authorization: str = Header(default=""), db: Session = Depends(get_db)):
    admin_from_token(authorization, db)
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(404, "Product not found")

    changes = data.model_dump(exclude_unset=True)
    if "model_code" in changes and changes["model_code"] is not None:
        code = changes["model_code"].strip()
        clash = db.query(Product).filter(Product.model_code == code, Product.id != product_id).first()
        if clash:
            raise HTTPException(400, "Model code already exists")
        changes["model_code"] = code
    for key in ("model_code", "name", "price", "stock", "warranty_months", "active"):
        if key in changes and changes[key] is None:
            changes.pop(key)  # these columns can't be NULL
    for key, value in changes.items():
        setattr(p, key, value)
    db.commit()
    return {"message": "Product updated"}


@router.get("/admin/orders")
def admin_orders(status: str = Query(default=""), authorization: str = Header(default=""),
                 db: Session = Depends(get_db)):
    admin_from_token(authorization, db)
    q = db.query(Order)
    if status in ("pending", "confirmed", "shipped", "completed", "cancelled"):
        q = q.filter(Order.status == status)
    orders = q.order_by(Order.created_at.desc()).limit(200).all()
    users = {u.id: u.username for u in db.query(User).filter(User.id.in_({o.user_id for o in orders})).all()} if orders else {}
    return _orders_payload(db, orders, users)


@router.patch("/admin/orders/{order_id}")
def admin_update_order(order_id: int, data: OrderUpdate,
                       authorization: str = Header(default=""), db: Session = Depends(get_db)):
    admin_from_token(authorization, db)
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(404, "Order not found")
    if order.status == "cancelled" and data.status != "cancelled":
        raise HTTPException(400, "คำสั่งซื้อที่ยกเลิกแล้วเปิดกลับไม่ได้ ให้สร้างคำสั่งซื้อใหม่")
    if data.status == "cancelled" and order.status != "cancelled":
        _restock(db, order.id)

    # Assign real, pre-registered machine serial numbers to the buyer only when
    # the order first becomes completed. Device.model_name must match Product.name.
    assigned_count = 0
    if data.status == "completed" and order.status != "completed":
        items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
        assignments = []
        for item in items:
            product = db.query(Product).filter(Product.id == item.product_id).first() if item.product_id else None
            if not product:
                raise HTTPException(400, f"找不到สินค้า {item.product_name}，ไม่สามารถผูกเครื่องได้")
            available = (db.query(Device)
                         .filter(Device.user_id.is_(None), Device.model_name == product.name)
                         .order_by(Device.id.asc()).limit(item.quantity).all())
            if len(available) < item.quantity:
                raise HTTPException(
                    400,
                    f"สินค้า {product.name} ต้องใช้เครื่อง {item.quantity} เครื่อง แต่มีเครื่องที่ลงทะเบียนและยังไม่ผูกบัญชีเพียง {len(available)} เครื่อง กรุณาเพิ่ม Serial Number ในเมนูจัดการเครื่องก่อน"
                )
            assignments.extend((device, product) for device in available)

        today = date.today()
        for device, product in assignments:
            device.user_id = order.user_id
            device.purchased_at = today
            months = max(0, int(product.warranty_months or 0))
            month_index = today.month - 1 + months
            year = today.year + month_index // 12
            month = month_index % 12 + 1
            day = min(today.day, calendar.monthrange(year, month)[1])
            device.warranty_until = date(year, month, day)
            assigned_count += 1

    order.status = data.status
    order.updated_at = datetime.utcnow()
    db.commit()
    message = "Order updated"
    if assigned_count:
        message += f"; assigned {assigned_count} device(s) to customer account"
    return {"message": message, "status": order.status, "assigned_devices": assigned_count}
