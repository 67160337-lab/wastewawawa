FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY frontend ./frontend
COPY water_treatment_ai_v1.pkl .
COPY data ./data

RUN mkdir -p /app/data

ENV MOCK_SENSOR=true
ENV SENSOR_SAVE_INTERVAL=30

EXPOSE 10000

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
