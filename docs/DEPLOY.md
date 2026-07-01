# Deploying SyllabusSlayer

Topology: **Vercel** hosts the two Next.js apps · **Render** hosts the FastAPI backend (Docker) · **Supabase** provides Postgres + Auth. All free-tier friendly.

```
teacher.vercel.app ─┐
                    ├─► Render (FastAPI) ─► Supabase Postgres
student.vercel.app ─┘        ▲
        └──────── Supabase Auth (JWT) ─────┘
```

---

## 1. Supabase (already set up)

You already have the project + keys. Two more things for prod:

- **Postgres connection string** — Supabase → *Project Settings → Database → Connection string*. Use the **Session pooler** (or direct) URI and rewrite the scheme for psycopg:
  ```
  postgresql+psycopg://postgres.<ref>:<db-password>@<host>:5432/postgres?sslmode=require
  ```
  This is the backend's `DATABASE_URL`.
- **Auth URLs** — Supabase → *Authentication → URL Configuration*: add your Vercel app URLs to **Site URL** / **Redirect URLs** so email links resolve. For a frictionless demo you can keep "Confirm email" off.
- *(Optional, later)* `create extension if not exists vector;` — only needed if/when we move chunk retrieval into pgvector (currently retrieval is in-memory at generation time).

Tables are created automatically on first backend boot (`init_db()` / `create_all`).

## 2. Backend → Render (Docker)

1. Render → **New → Blueprint**, point it at this repo. It reads `render.yaml` (Docker web service, `backend/Dockerfile`, `/health` check).
2. Set the secret env vars (marked `sync: false`):

   | Var | Value |
   |---|---|
   | `DATABASE_URL` | the Supabase psycopg URI from step 1 |
   | `OPENAI_API_KEY` | your OpenAI key |
   | `SUPABASE_URL` | `SUPABASE_URL` from root `.env` |
   | `SUPABASE_JWKS_URL` | `SUPABASE_JWKS_URL` from root `.env` |
   | `CORS_ORIGINS` | JSON list of the Vercel URLs, e.g. `["https://ss-teacher.vercel.app","https://ss-student.vercel.app"]` |

   `ENV=prod` (set in the blueprint) disables the dev auth shim — only real Supabase tokens are accepted.
3. Deploy → note the API URL, e.g. `https://syllabusslayer-api.onrender.com`.

> Free Render services sleep when idle (first request cold-starts ~50s). Fine for a demo.

## 3. Frontends → Vercel (two projects, one repo)

For **each** app (teacher, then student), create a Vercel project from this repo:

1. **Root Directory** = `apps/teacher` (then a second project with `apps/student`). Framework auto-detects **Next.js**; Vercel installs the npm workspace from the repo root, so the shared package resolves (it's listed in `transpilePackages`).
2. Env vars (both apps):

   | Var | Value |
   |---|---|
   | `NEXT_PUBLIC_SUPABASE_URL` | `SUPABASE_URL` |
   | `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | `SUPABASE_PUBLISHABLE_KEY` |
   | `NEXT_PUBLIC_API_URL` | the Render API URL from step 2 |
3. Deploy → note the two app URLs.

## 4. Wire CORS + Auth URLs

- Put the two Vercel URLs into Render's `CORS_ORIGINS` (step 2) and redeploy the backend.
- Add the two Vercel URLs to Supabase Auth's Site/Redirect URLs (step 1).

## 5. Smoke test

1. Open the **teacher** app → sign up (role `teacher`) → create a class → note the join code.
2. Generate a campaign (upload a doc via the teacher API / `scripts/m1_demo.py` seeds one) → review → assign to the class.
3. Open the **student** app → sign up (role `student`) → join with the code → play.
4. Back in the teacher app → the class dashboard shows the student's attempts + mastery.

## Notes / follow-ups
- **Migrations:** tables are auto-created; adopt **Alembic** before making breaking schema changes in prod.
- **Secrets:** never commit `.env` / `.env.local` (git-ignored). Set all secrets in the Render / Vercel dashboards.
- **Model ids/pricing** are pinned as env vars — re-verify on the OpenAI pricing page periodically.
