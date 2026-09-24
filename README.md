# Perfect Saturday Planner backend

Small, stateless FastAPI service with mocked activity and food data. It is
intended to run separately from the frontend and has permissive CORS enabled.

## Run locally

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Endpoints:

- `GET /health` (also available at `/api/health`)
- `POST /api/plan`
- Interactive API documentation: `http://localhost:8000/docs`

Example request:

```json
{
  "city": "Bangalore",
  "budget": 1500,
  "available_time": "6 hours",
  "mood": "relaxed",
  "interests": ["nature", "food"],
  "constraints": ["vegetarian"]
}
```

## Deploy for free

No environment variables are required. Create a Python service on **Render**
or **Railway**, set the root directory to `backend` (if deploying the
repository), and use:

- Build/install command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

Render's free web service and Railway's free/trial service both provide a
public URL that the frontend can call. The service uses only in-memory mocked
data and does not require a database.
