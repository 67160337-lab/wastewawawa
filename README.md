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
