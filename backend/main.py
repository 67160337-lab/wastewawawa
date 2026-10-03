import os
import time
import joblib
import pandas as pd

from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from backend.database import Base, engine, get_db, SessionLocal, DATABASE_URL
from backend.models import User, WaterQuality, AIPrediction
from backend.schemas import RegisterRequest, LoginRequest, WaterRequest, PredictionRequest, AdminRoleUpdate
from backend.auth import hash_password, verify_password
from backend.mock_sensor import get_sensor_data
from sqlalchemy import text

os.makedirs("data", exist_ok=True)
Base.metadata.create_all(bind=engine)


def _migrate_sqlite_add_is_admin():
    """Older deployments' SQLite files won't have the is_admin column yet.
    create_all() only creates missing tables, not missing columns, so add it here."""
    if not DATABASE_URL.startswith("sqlite"):
        return
    try:
        with engine.connect() as conn:
            cols = [row[1] for row in conn.execute(text("PRAGMA table_info(users)"))]
            if "is_admin" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0"))
                conn.commit()
                print("Migrated: added is_admin column to users table.")
    except Exception as e:
        print(f"Warning: is_admin migration skipped: {e}")


def _bootstrap_admin():
    """Set ADMIN_USERNAME env var to grant that existing user admin rights on startup."""
    admin_username = os.getenv("ADMIN_USERNAME")
    if not admin_username:
        return
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == admin_username).first()
        if user and not user.is_admin:
            user.is_admin = True
            db.commit()
            print(f"Granted admin access to '{admin_username}' via ADMIN_USERNAME.")
        elif not user:
            print(f"ADMIN_USERNAME='{admin_username}' set, but that user doesn't exist yet.")
    finally:
        db.close()


def _migrate_sqlite_add_indexes():
    """create_all() only builds indexes for brand-new tables, not ones that
    already exist (same issue as the is_admin column above). CREATE INDEX IF
    NOT EXISTS is idempotent, so it's safe to run on every startup."""
    if not DATABASE_URL.startswith("sqlite"):
        return
    statements = [
        "CREATE INDEX IF NOT EXISTS idx_water_user_created ON water_quality (user_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_water_created ON water_quality (created_at)",
        "CREATE INDEX IF NOT EXISTS idx_pred_user_created ON ai_predictions (user_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_pred_created ON ai_predictions (created_at)",
    ]
    try:
        with engine.connect() as conn:
            for stmt in statements:
                conn.execute(text(stmt))
            conn.commit()
    except Exception as e:
        print(f"Warning: index migration skipped: {e}")


_migrate_sqlite_add_is_admin()
_migrate_sqlite_add_indexes()
_bootstrap_admin()

app = FastAPI(title="Wastewater AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "water_treatment_ai_v1.pkl"
)

try:
    ai_model = joblib.load(MODEL_PATH)
    print("AI Model loaded successfully.")
except Exception as e:
    ai_model = None
    print(f"Warning: Could not load AI Model. Fallback formula will be used. Error: {e}")

FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "frontend"
)

# In-memory limiter: do not write to SQLite on every 2-second dashboard request.
_last_sensor_save = {}
SENSOR_SAVE_INTERVAL = int(os.getenv("SENSOR_SAVE_INTERVAL", "30"))


def user_from_token(authorization: str, db: Session):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Please login")

    username = authorization.replace("Bearer ", "", 1)
    user = db.query(User).filter(User.username == username).first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")

    # Self-heals the ADMIN_USERNAME grant on every authenticated request,
    # instead of only once at process startup. This matters because on
    # Render's free plan, the SQLite file is wiped on every deploy, so the
    # target account may not have existed yet when the server first booted.
    admin_username = os.getenv("ADMIN_USERNAME")
    if admin_username and user.username == admin_username and not user.is_admin:
        user.is_admin = True
        db.commit()
        db.refresh(user)

    return user


def admin_from_token(authorization: str, db: Session):
    user = user_from_token(authorization, db)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def calculate_speed(data):
    if ai_model is not None:
        input_data = pd.DataFrame([{
            "influent_cod": data["influent_cod"],
            "flow_rate": data["flow_rate"],
            "water_temp": data["water_temp"],
            "current_do": data["current_do"]
        }])
        speed = float(ai_model.predict(input_data)[0])
    else:
        speed = (
            35
            + data["influent_cod"] * 0.08
            + data["flow_rate"] * 0.25
            + max(0, 4 - data["current_do"]) * 8
            + max(0, data["water_temp"] - 30) * 0.5
        )

    return max(0.0, min(100.0, speed))


@app.get("/")
def root():
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Wastewater AI API is running"}


@app.get("/health")
def health():
    return {"status": "ok", "mock_sensor": os.getenv("MOCK_SENSOR", "true")}


@app.post("/register")
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(400, "Username already exists")
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(400, "Email already exists")

    user = User(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password)
    )
    db.add(user)
    db.commit()
    return {"message": "Register successful"}


@app.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Username or password is incorrect")

    admin_username = os.getenv("ADMIN_USERNAME")
    if admin_username and user.username == admin_username and not user.is_admin:
        user.is_admin = True
        db.commit()
        db.refresh(user)

    return {
        "message": "Login successful",
        "token": user.username,
        "user": {"id": user.id, "username": user.username, "email": user.email, "is_admin": user.is_admin}
    }


@app.get("/me")
def me(authorization: str = Header(default=""), db: Session = Depends(get_db)):
    user = user_from_token(authorization, db)
    return {"id": user.id, "username": user.username, "email": user.email, "is_admin": user.is_admin}


@app.get("/sensor/live")
def live_sensor(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db)
):
    user = user_from_token(authorization, db)

    data = get_sensor_data()
    speed = calculate_speed(data)

    # Save one live snapshot every N seconds for the logged-in user's history.
    now = time.time()
    previous = _last_sensor_save.get(user.id, 0)

    if now - previous >= SENSOR_SAVE_INTERVAL:
        water = WaterQuality(
            user_id=user.id,
            influent_cod=data["influent_cod"],
            flow_rate=data["flow_rate"],
            water_temp=data["water_temp"],
            current_do=data["current_do"],
            status="ปกติ" if data["current_do"] >= 4 else "ควรเฝ้าระวัง"
        )

        prediction = AIPrediction(
            user_id=user.id,
            influent_cod=data["influent_cod"],
            flow_rate=data["flow_rate"],
            water_temp=data["water_temp"],
            current_do=data["current_do"],
            predicted_speed=round(speed, 2)
        )

        db.add(water)
        db.add(prediction)
        db.commit()
        _last_sensor_save[user.id] = now

    return {
        **data,
        "predicted_speed": round(speed, 2),
        "mode": "อัตโนมัติ",
        "sensor_interval_seconds": 2
    }


@app.post("/water")
def save_water(
    data: WaterRequest,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db)
):
    user = user_from_token(authorization, db)
    status = "ปกติ" if data.current_do >= 4 else "ควรเฝ้าระวัง"

    row = WaterQuality(user_id=user.id, status=status, **data.model_dump())
    db.add(row)
    db.commit()

    return {"message": "Water quality saved", "status": status}


@app.get("/water")
def water_history(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db)
):
    user = user_from_token(authorization, db)

    rows = (
        db.query(WaterQuality)
        .filter(WaterQuality.user_id == user.id)
        .order_by(WaterQuality.created_at.desc())
        .all()
    )

    return [{
        "id": r.id,
        "influent_cod": r.influent_cod,
        "flow_rate": r.flow_rate,
        "water_temp": r.water_temp,
        "current_do": r.current_do,
        "status": r.status,
        "created_at": r.created_at.isoformat()
    } for r in rows]


@app.post("/prediction")
def prediction(
    data: PredictionRequest,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db)
):
    user = user_from_token(authorization, db)
    speed = calculate_speed(data.model_dump())

    row = AIPrediction(
        user_id=user.id,
        predicted_speed=round(speed, 2),
        **data.model_dump()
    )
    db.add(row)
    db.commit()

    return {
        "predicted_speed": round(speed, 2),
        "message": "Prediction successful"
    }


@app.get("/predictions")
def prediction_history(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db)
):
    user = user_from_token(authorization, db)

    rows = (
        db.query(AIPrediction)
        .filter(AIPrediction.user_id == user.id)
        .order_by(AIPrediction.created_at.desc())
        .all()
    )

    return [{
        "id": r.id,
        "influent_cod": r.influent_cod,
        "flow_rate": r.flow_rate,
        "water_temp": r.water_temp,
        "current_do": r.current_do,
        "predicted_speed": r.predicted_speed,
        "created_at": r.created_at.isoformat()
    } for r in rows]


# ---------------------------------------------------------------------------
# Admin-only endpoints: manage user accounts and view data across all users.
# ---------------------------------------------------------------------------

@app.get("/admin/users")
def admin_list_users(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db)
):
    admin_from_token(authorization, db)

    users = db.query(User).order_by(User.created_at.asc()).all()
    return [{
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "is_admin": u.is_admin,
        "created_at": u.created_at.isoformat()
    } for u in users]


@app.patch("/admin/users/{user_id}")
def admin_set_role(
    user_id: int,
    data: AdminRoleUpdate,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db)
):
    admin = admin_from_token(authorization, db)

    if user_id == admin.id and not data.is_admin:
        raise HTTPException(400, "You cannot remove your own admin access")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(404, "User not found")

    target.is_admin = data.is_admin
    db.commit()

    return {"message": "Role updated", "id": target.id, "is_admin": target.is_admin}


@app.delete("/admin/users/{user_id}")
def admin_delete_user(
    user_id: int,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db)
):
    admin = admin_from_token(authorization, db)

    if user_id == admin.id:
        raise HTTPException(400, "You cannot delete your own account")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(404, "User not found")

    db.query(WaterQuality).filter(WaterQuality.user_id == user_id).delete()
    db.query(AIPrediction).filter(AIPrediction.user_id == user_id).delete()
    db.delete(target)
    db.commit()

    return {"message": "User deleted"}


@app.get("/admin/water")
def admin_all_water(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db)
):
    admin_from_token(authorization, db)

    rows = (
        db.query(WaterQuality, User.username)
        .join(User, WaterQuality.user_id == User.id)
        .order_by(WaterQuality.created_at.desc())
        .limit(500)
        .all()
    )

    return [{
        "id": r.WaterQuality.id,
        "username": r.username,
        "influent_cod": r.WaterQuality.influent_cod,
        "flow_rate": r.WaterQuality.flow_rate,
        "water_temp": r.WaterQuality.water_temp,
        "current_do": r.WaterQuality.current_do,
        "status": r.WaterQuality.status,
        "created_at": r.WaterQuality.created_at.isoformat()
    } for r in rows]


@app.get("/admin/predictions")
def admin_all_predictions(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db)
):
    admin_from_token(authorization, db)

    rows = (
        db.query(AIPrediction, User.username)
        .join(User, AIPrediction.user_id == User.id)
        .order_by(AIPrediction.created_at.desc())
        .limit(500)
        .all()
    )

    return [{
        "id": r.AIPrediction.id,
        "username": r.username,
        "influent_cod": r.AIPrediction.influent_cod,
        "flow_rate": r.AIPrediction.flow_rate,
        "water_temp": r.AIPrediction.water_temp,
        "current_do": r.AIPrediction.current_do,
        "predicted_speed": r.AIPrediction.predicted_speed,
        "created_at": r.AIPrediction.created_at.isoformat()
    } for r in rows]


@app.get("/admin/explain")
def admin_explain_indexes(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db)
):
    """Shows SQLite's query plan for the app's real queries, so you can see
    the indexes actually being picked up (look for 'USING INDEX' in the
    output) — the same idea as EXPLAIN ANALYZE in the indexing lab, applied
    to this project's own tables instead of the lab's sample data."""
    admin_from_token(authorization, db)

    if not DATABASE_URL.startswith("sqlite"):
        return {"message": "This endpoint only formats SQLite's EXPLAIN QUERY PLAN output."}

    queries = {
        "Water history for one user (WHERE user_id + ORDER BY created_at)":
            "EXPLAIN QUERY PLAN SELECT * FROM water_quality WHERE user_id = 1 ORDER BY created_at DESC",
        "Predictions for one user (WHERE user_id + ORDER BY created_at)":
            "EXPLAIN QUERY PLAN SELECT * FROM ai_predictions WHERE user_id = 1 ORDER BY created_at DESC",
        "Admin: latest 500 water records (ORDER BY created_at only)":
            "EXPLAIN QUERY PLAN SELECT * FROM water_quality ORDER BY created_at DESC LIMIT 500",
        "Admin: latest 500 predictions (ORDER BY created_at only)":
            "EXPLAIN QUERY PLAN SELECT * FROM ai_predictions ORDER BY created_at DESC LIMIT 500",
        "Login lookup (WHERE username =)":
            "EXPLAIN QUERY PLAN SELECT * FROM users WHERE username = 'demo'",
    }

    result = []
    with engine.connect() as conn:
        for label, sql in queries.items():
            rows = conn.execute(text(sql)).fetchall()
            result.append({
                "query": label,
                "sql": sql,
                "plan": [" | ".join(str(c) for c in row) for row in rows]
            })

    return result


# Serve existing HTML/CSS/JS files.
app.mount(
    "/css",
    StaticFiles(directory=os.path.join(FRONTEND_DIR, "css")),
    name="css"
)
app.mount(
    "/js",
    StaticFiles(directory=os.path.join(FRONTEND_DIR, "js")),
    name="js"
)


@app.get("/{page_name}.html")
def frontend_page(page_name: str):
    page_file = os.path.join(FRONTEND_DIR, f"{page_name}.html")

    # Prevent path traversal while keeping the existing multi-page frontend.
    if not os.path.abspath(page_file).startswith(os.path.abspath(FRONTEND_DIR)):
        raise HTTPException(status_code=404, detail="Page not found")

    if not os.path.exists(page_file):
        raise HTTPException(status_code=404, detail="Page not found")

    return FileResponse(page_file)
