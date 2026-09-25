import os
import time
import joblib
import pandas as pd

from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from backend.database import Base, engine, get_db
from backend.models import User, WaterQuality, AIPrediction
from backend.schemas import RegisterRequest, LoginRequest, WaterRequest, PredictionRequest
from backend.auth import hash_password, verify_password
from backend.mock_sensor import get_sensor_data

os.makedirs("data", exist_ok=True)
Base.metadata.create_all(bind=engine)

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

    return {
        "message": "Login successful",
        "token": user.username,
        "user": {"id": user.id, "username": user.username, "email": user.email}
    }


@app.get("/me")
def me(authorization: str = Header(default=""), db: Session = Depends(get_db)):
    user = user_from_token(authorization, db)
    return {"id": user.id, "username": user.username, "email": user.email}


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
            status="Good" if data["current_do"] >= 4 else "Needs Attention"
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
        "mode": "AUTO",
        "sensor_interval_seconds": 2
    }


@app.post("/water")
def save_water(
    data: WaterRequest,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db)
):
    user = user_from_token(authorization, db)
    status = "Good" if data.current_do >= 4 else "Needs Attention"

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
