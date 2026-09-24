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

### Vercel (serverless FastAPI)

This repository includes [`api/index.py`](./api/index.py) as the Vercel
serverless entrypoint and [`vercel.json`](./vercel.json) for function
configuration.

In Vercel, import this repository and leave the project root at the
repository root. Vercel detects the Python function under `api/` and installs
packages from `requirements.txt`. No environment variables are required.

After deployment, verify:

- `https://YOUR-PROJECT.vercel.app/health`
- `https://YOUR-PROJECT.vercel.app/docs`
- `https://YOUR-PROJECT.vercel.app/api/health`

Set the frontend's `VITE_API_URL` to the project URL without a trailing slash.
The frontend already appends `/api/plan`.

Vercel's Python runtime is serverless, so it is stateless and may have a short
cold start. This app is suitable because it uses only in-memory mock data and
completes each request quickly.

### Render or Railway

No environment variables are required. Create a Python service on **Render**
or **Railway**, set the root directory to `backend` (if deploying the
repository), and use:

- Build/install command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

Render's free web service and Railway's free/trial service both provide a
public URL that the frontend can call. The service uses only in-memory mocked
data and does not require a database.
