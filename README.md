# ARX — 24+ Model AI Chat Platform

Local multi-model chat UI over 24+ frontier LLMs (11 providers), streaming SSE, hybrid RAG, runtime model registry, and a 4-layer security perimeter.

Everything runs on your machine. There is no Docker requirement and no cloud deploy step.

## What you must provide

1. **MongoDB** running locally, database `arx`  
   Connection used by the backend: `mongodb://localhost:27017/arx`
2. **OPENROUTER_API_KEY** in `arx/backend/.env`  
   Leave it empty and the app still boots; live inference and the 300ms first-token check need a real key.
3. Generated **JWT_SECRET** and **INTERNAL_API_KEY** are already in the `.env` files. Open `arx/backend/.env` (and the matching value in `arx/frontend/.env.local`). Do not commit those files.

The first registered user is promoted to **admin**.

Unknown OpenRouter list prices are stored as `null` in the registry (xAI, Moonshot, Qwen, Nvidia, MiniMax, and some Meta/Mistral variants). They are not invented.

## How to run

Run these from the repository root after cloning.

### Backend

```powershell
cd arx/backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Health check: `GET http://localhost:8000/health` → `{"mongo": true}` when Mongo is up.

### Frontend

```powershell
cd arx/frontend
npm install
npm run dev
```

Open `http://localhost:3000`. The browser talks only to Next.js route handlers. Those handlers attach `X-Internal-Key` and the JWT from an httpOnly cookie. The browser never holds those secrets.

### Tests

```powershell
cd arx/backend
.venv\Scripts\activate
pytest
```

## Request pipeline

`POST /api/chat` runs six separately testable stages:

1. Security (`services/security.py`)
2. Quota (`services/quota.py`)
3. Retrieval (`services/retrieval.py`)
4. Routing (`services/router.py`)
5. Inference (`services/llm.py`)
6. SSE stream-out (`routers/chat.py`)

## Notes

- LiteLLM model ids are `openrouter/<provider>/<model>` with `api_base=OPENROUTER_BASE_URL`.
- Model registry cache TTL is 60s and is invalidated on admin writes. Adding a model does not require a restart.
- Quota is global across models. Exceeding it returns HTTP 429 with `limit`, `used`, and `resets_at`.
- Cancelled streams are not billed for undelivered tokens.
- FastEmbed model `BAAI/bge-small-en-v1.5` downloads on first RAG ingest.
