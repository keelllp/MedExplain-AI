# Deploying MedExplain AI

The app is split for hosting:

- **Frontend (Next.js)** → **Vercel** (static/edge, what it's built for).
- **Backend (FastAPI)** → an **always-on container with a persistent disk** (Render / Railway /
  Fly.io, or any VPS). It is a *stateful single-process server* — SQLite on local disk, uploaded
  files on local disk, an in-process job semaphore that owns warm-loaded models, and background
  analysis. That model needs a persistent filesystem and a long-lived process, so it **cannot run
  on serverless** (Vercel functions, Cloud Run as-is, etc.).

Keep the LLM on **Gemini (cloud)** so you don't have to host Ollama (a local model needs a big
always-on box). The backend already defaults new accounts to cloud/Gemini.

---

## 1. Backend container

### Test it locally first

```bash
# from the repo root (the build context must be the repo root — it also needs knowledge_base/)
docker compose up --build          # → http://localhost:8000/health and /docs
```

`docker-compose.yml` reuses `backend/.env` (your Gemini key) and runs in dev mode so it boots
with the default JWT secret, mounting `./data` for the SQLite DB + uploads.

Build the image directly instead:

```bash
docker build -f backend/Dockerfile -t medexplain-backend .
docker run -p 8000:8000 \
  -e MEDEXPLAIN_ENV=prod \
  -e MEDEXPLAIN_JWT_SECRET="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')" \
  -e MEDEXPLAIN_CORS_ORIGINS="https://your-app.vercel.app" \
  -e MEDEXPLAIN_GEMINI_API_KEY="AIza..." \
  -e MEDEXPLAIN_DEFAULT_LLM_MODE=cloud \
  -v "$(pwd)/data:/app/data" \
  medexplain-backend
```

**OCR (scanned/image uploads):** off by default to keep the image small + the build reliable
(native-text PDFs work without it). Bake it in with `--build-arg INSTALL_OCR=true` (or set the
arg in `docker-compose.yml`).

### Deploy to Render (turnkey, via `render.yaml`)

1. Push the repo to GitHub.
2. Render → **New → Blueprint** → select the repo. It reads `render.yaml` (Docker web service +
   a 1 GB persistent disk at `/app/data`, single instance).
3. In the dashboard, set the two secret env vars:
   - `MEDEXPLAIN_GEMINI_API_KEY` — your Gemini key.
   - `MEDEXPLAIN_CORS_ORIGINS` — your Vercel URL (e.g. `https://your-app.vercel.app`). Comma-
     separate if you have several; **no `*`** (the app refuses `*` with credentials in prod).
4. Deploy. Health check is `GET /health`. Note the service URL, e.g.
   `https://medexplain-backend.onrender.com`.

> A persistent disk needs a paid instance (free has none). The disk + SQLite pin it to **one
> instance** — which is exactly the single-worker design. Do not scale out.

### Or Railway / Fly.io / a VPS

Same container, same two requirements — **a persistent volume mounted at `/app/data`** and the
env vars below:

- **Railway:** new service from the Dockerfile, add a Volume mounted at `/app/data`, set the env.
- **Fly.io:** `fly launch` (uses `backend/Dockerfile`), `fly volumes create medexplain_data`,
  mount it at `/app/data` in `fly.toml`, set secrets with `fly secrets set ...`.
- **VPS:** `docker compose up -d` with `MEDEXPLAIN_ENV=prod` + a real JWT secret in `.env`, and
  put it behind a reverse proxy (Caddy/Nginx) for TLS.

### Backend env vars

| Var | Required | Notes |
|---|---|---|
| `MEDEXPLAIN_ENV` | yes | `prod` in production (refuses the default JWT secret + `*` CORS). |
| `MEDEXPLAIN_JWT_SECRET` | yes (prod) | Long random string. Render `generateValue`s it. |
| `MEDEXPLAIN_CORS_ORIGINS` | yes | Your Vercel origin(s), comma-separated. No `*`. |
| `MEDEXPLAIN_GEMINI_API_KEY` | for cloud LLM | Empty → falls back to offline templates (no egress). |
| `MEDEXPLAIN_DEFAULT_LLM_MODE` | no | `cloud` (default) or `offline`. |
| `MEDEXPLAIN_GEMINI_MODEL` | no | `gemini-2.5-flash`. |
| `MEDEXPLAIN_MAX_UPLOAD_MB` | no | `20`. |

State lives under `/app/data` (`medexplain.db` + `uploads/`) — that's the only thing to back up.

---

## 2. Frontend on Vercel

1. Vercel → **Add New → Project** → import the repo.
2. Set **Root Directory = `frontend`** (the Next.js app lives in a subfolder). Framework
   auto-detects as Next.js.
3. Add an environment variable (Production + Preview):
   - `NEXT_PUBLIC_API_BASE_URL` = `https://<your-backend-url>/api/v1`
     (e.g. `https://medexplain-backend.onrender.com/api/v1`).
4. Deploy. Then go back and make sure the backend's `MEDEXPLAIN_CORS_ORIGINS` includes the final
   Vercel domain (and any custom domain). Redeploy the backend if you changed it.

> `NEXT_PUBLIC_*` is inlined at build time, so changing it requires a redeploy.

---

## 3. Wiring checklist

- [ ] Backend up, `GET /health` returns `{"status":"ok"}`.
- [ ] `MEDEXPLAIN_CORS_ORIGINS` = the exact Vercel origin (scheme + host, no trailing slash).
- [ ] Vercel `NEXT_PUBLIC_API_BASE_URL` = backend URL **+ `/api/v1`**.
- [ ] Persistent disk mounted at `/app/data` (else the DB + uploads vanish on redeploy).
- [ ] A strong `MEDEXPLAIN_JWT_SECRET` in prod.

## Privacy note

This handles medical data. The **free Gemini tier may use your inputs to improve Google's
models**, so it is not appropriate for real patient data — for production PHI use paid **Vertex
AI** (with a BAA) and a host you trust. Uploaded files + the DB stay on your backend's disk;
nothing is sent anywhere except the LLM provider you configure.
