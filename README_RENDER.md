# Wastewater AI - Docker + Mock Real-time Sensor Patch

This patch is designed to be copied into the existing `67160337-lab/wastewatarAItest` repository.

## Added/changed
- `backend/mock_sensor.py` - generates smooth mock DO/COD/flow/temperature values.
- `backend/main.py` - adds `/sensor/live`, AI prediction from live values, periodic history saving, and serves the existing frontend.
- `backend/database.py` - supports `DATABASE_URL`.
- `frontend/dashboard.html` - live sensor dashboard.
- `frontend/js/dashboard.js` - polls live data every 2 seconds.
- `frontend/js/api.js` - uses same-origin API, so the Render URL can be used without hard-coding the old backend URL.
- `Dockerfile` - Render-compatible Docker image.
- `docker-compose.yml` - optional local Docker configuration.
- `.dockerignore`
- `render.yaml` - optional Render Blueprint configuration.

## Important
You do NOT need to run Docker on your computer for deployment. Render can build the Docker image directly from the Dockerfile in GitHub.

The existing AI model file `water_treatment_ai_v1.pkl` is still expected at the repository root.

The mock sensor is enabled with:
`MOCK_SENSOR=true`

The dashboard requests `/sensor/live` every 2 seconds. To avoid filling SQLite, only one snapshot per user is saved every 30 seconds.

For production persistence on Render, attach a Persistent Disk at `/app/data`, or move the database to PostgreSQL later.
