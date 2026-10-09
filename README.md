## Database Index Optimization

ปรับปรุงประสิทธิภาพการ Query ฐานข้อมูล โดยเพิ่ม Index ให้สอดคล้องกับรูปแบบการใช้งานจริงของระบบ และเพิ่มเครื่องมือสำหรับตรวจสอบว่า Index ถูกนำไปใช้งานจริงหรือไม่

### รายการปรับปรุง

| ไฟล์ / ส่วนที่แก้ไข            | รายละเอียด                                                                                                                                                                                                                   |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/models.py`            | เพิ่ม **Composite Index `(user_id, created_at)`** บนตาราง `water_quality` และ `ai_predictions` เพื่อรองรับ Query ที่ใช้จริงในระบบ เช่น `WHERE user_id = ? ORDER BY created_at DESC` ซึ่งถูกใช้งานในหน้าต่าง ๆ ของระบบ        |
| `backend/models.py`            | เพิ่ม **Index เดี่ยวบน `created_at`** เพื่อรองรับหน้า Admin ที่ดึงข้อมูลล่าสุด 500 รายการจากผู้ใช้ทั้งหมด โดยไม่มีการ Filter ด้วย `user_id`                                                                                  |
| `backend/main.py`              | เพิ่ม Migration ด้วย `CREATE INDEX IF NOT EXISTS` เพื่อสร้าง Index อัตโนมัติเมื่อระบบ Startup รองรับทั้ง **Database เดิมที่มีข้อมูลอยู่แล้ว** และ **Database ใหม่** โดยไม่ต้องสร้าง Index ด้วยตนเอง                          |
| `backend/main.py` + หน้า Admin | เพิ่มปุ่ม **Check Index Usage** ในหน้า Admin สำหรับตรวจสอบการใช้งาน Index โดยแสดงผลจาก `EXPLAIN QUERY PLAN` ของ Query ที่ใช้จริงในระบบ ทำให้สามารถตรวจสอบได้ว่า Database มีการเลือกใช้ Index หรือไม่ เช่น แสดง `USING INDEX` |

การเพิ่ม Index ช่วยให้ Database สามารถค้นหาและเรียงลำดับข้อมูลได้มีประสิทธิภาพมากขึ้น โดยเฉพาะเมื่อจำนวนข้อมูลเพิ่มขึ้นในอนาคต

### Index ที่เพิ่ม

```text
water_quality
├── (user_id, created_at)
└── created_at

ai_predictions
└── (user_id, created_at)
```

### ตรวจสอบการใช้งาน Index

หน้า Admin มีปุ่ม **Check Index Usage** สำหรับตรวจสอบ Query Plan ของ Query จริง โดยใช้:

```sql
EXPLAIN QUERY PLAN
```

ตัวอย่างผลลัพธ์ที่ต้องการตรวจสอบ:

```text
USING INDEX
```

ซึ่งช่วยให้สามารถยืนยันได้ว่า Index ที่สร้างขึ้นถูก Database นำมาใช้กับ Query จริง ไม่ได้เป็นเพียงการสร้าง Index ไว้เฉย ๆ

Current DO → ค่าออกซิเจนละลายน้ำปัจจุบัน (DO)
ปริมาณออกซิเจนที่ละลายอยู่ในน้ำ ใช้เลี้ยงจุลินทรีย์ในระบบบำบัดน้ำเสีย
หน่วย: mg/L (มิลลิกรัมต่อลิตร)
ค่ายิ่งสูง = ออกซิเจนเพียงพอเลี้ยงจุลินทรีย์เก็บน้ำเสีย → ระบบทำงานดี

Temperature → อุณหภูมิน้ำ
อุณหภูมิของน้ำเสียที่เข้าสู่ระบบบำบัด
หน่วย: °C
มีผลต่ออัตราการย่อยสลายของจุลินทรีย์และการละลายออกซิเจน

COD → ค่าซีโอดี (สารอินทรีย์ปนเปื้อนในน้ำเสีย)
ค่าความต้องการออกซิเจนทางเคมี วัดระดับสิ่งสกปรกอินทรีย์ในน้ำเสีย
หน่วย: mg/L
ค่ายิ่งสูง = น้ำเสียยิ่งสกปรก ต้องใช้ออกซิเจนบำบัดมากขึ้น

Flow Rate → อัตราการไหลของน้ำ
ปริมาณน้ำเสียที่ไหลเข้าสู่ระบบบำบัดต่อหน่วยเวลา
หน่วย: m³/h (ลูกบาศก์เมตรต่อชั่วโมง)
กำหนดขนาดการทำงานของระบบบำบัด


---

## Machine-sales dashboards

The dashboard is bundled with each water-treatment machine sold.

| Role | Landing page | What they see |
|---|---|---|
| Customer | `dashboard.html` | Status banner (green/yellow/red + plain-language advice), their machine(s) and warranty, 24h summary, live sensor + AI aerator speed, `support.html` to send repair requests |
| Admin | `admin.html` | KPIs (customers, machines sold, machines needing attention, open repair requests, offline machines, warranties expiring), machine list with customer assignment, repair-request inbox, plus the existing user management / index check / all-records tables |

### New tables / endpoints
- `devices` (serial, model, owner, purchase date, warranty) and `service_requests`; `water_quality.device_id` links readings to a machine.
- Customer: `GET /me/overview`, `GET|POST /service-requests`
- Admin: `GET /admin/overview`, `GET|POST /admin/devices`, `PATCH|DELETE /admin/devices/{id}`, `GET /admin/service-requests`, `PATCH /admin/service-requests/{id}`
- Thresholds live in `backend/rules.py` (override with `DO_WARN`, `DO_CRIT`, `COD_WARN`, `TEMP_WARN`).

### Security change
Login tokens are now signed (HMAC). **Set `SECRET_KEY`** in your environment (`render.yaml` and `docker-compose.yml` already include it). Previously the token was just the username and could be forged.

### Shop (buy an aerator / air blower)
- Customers: `shop.html` — catalogue, "recommended for your flow rate" highlight (prefilled from their latest sensor reading), cart, order request, cancel while pending.
- Admin: `admin.html` — order inbox (confirm / ship / complete / cancel; cancelling restores stock) and product management (price, stock, on/off sale).
- No online payment: the seller confirms each order and arranges payment. Prices are always taken from the database, never from the browser.
- On first start, an empty catalogue is filled with 4 starter products (AB-15, AB-22, AB-37, AB-55; see `STARTER_PRODUCTS` in `backend/shop.py`). Their specs and prices are starting values: edit them in Admin > สินค้า. Set `SEED_PRODUCTS=false` to disable.
