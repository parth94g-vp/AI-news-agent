# Deploying: scheduler (#6) + daily email (#4)

This makes the agent run **every morning at 9 AM IST on its own**, even if your laptop is off,
and **email** the result to each user who's set an email address. Local Streamlit/React use
still works exactly as before and needs none of this.

## Two real constraints, read this first

**1. Render's Cron Jobs are not free** — they cost a minimum of $1/month even on an otherwise
free account, which is why Render asked you for payment info. So the scheduler below runs on
**GitHub Actions** instead (genuinely free, no card), and talks directly to the database and
APIs — it does not need Render at all. Render is only used for the backend the React app talks
to, which does have a real free tier.

**2. Render's free web service has an ephemeral filesystem**: a local SQLite file is **wiped**
on every deploy and periodic restart. Use a free hosted Postgres instead for anything deployed —
**[neon.tech](https://neon.tech)** (no credit card, doesn't expire with normal use). Local
SQLite is fine as long as you're only running on your own laptop.

If you'd rather skip cloud hosting entirely for now: keep running the agent locally (laptop on)
and use Windows Task Scheduler / cron to run `python scripts/run_scheduled_digest.py` at 9 AM —
your existing local SQLite file works fine for that.

## Step 1 — Gmail app password (for #4)

1. Google Account → **Security** → turn on **2-Step Verification** if it isn't already on.
2. Search settings for **App passwords** → create one, name it "AI News Agent".
3. Copy the 16-character code. You'll use it as `GMAIL_APP_PASSWORD` — never your normal
   Gmail password.

## Step 2 — push the project to GitHub

```bash
cd news-ai-agent
git init
git add .
git commit -m "AI news agent"
```
Create a new empty repository on GitHub, then:
```bash
git remote add origin https://github.com/<you>/<repo>.git
git branch -M main
git push -u origin main
```

## Step 3 — create the Postgres database (Neon)

1. neon.tech → sign up → New Project.
2. Copy the connection string (**Dashboard → Connection Details**), e.g.
   `postgresql://user:password@ep-xxx.neon.tech/neondb?sslmode=require`.
3. Keep it handy — you'll use it in both Step 4 and Step 5.

## Step 4 — set up the free scheduler (GitHub Actions)

The workflow file is already in the repo at `.github/workflows/daily-digest.yml`. You just need
to give it your secrets:

1. On GitHub, open your repo → **Settings** → **Secrets and variables** → **Actions**.
2. Click **New repository secret** and add each of these (one at a time):
   - `GROQ_API_KEY`
   - `NEWSDATA_API_KEY`
   - `GMAIL_ADDRESS`
   - `GMAIL_APP_PASSWORD`
   - `DATABASE_URL` — the Neon connection string from Step 3
3. That's it. It'll run automatically every day at 9 AM IST.
4. **To test it right now** instead of waiting until tomorrow: go to the **Actions** tab on
   GitHub → **Daily news digest** (left sidebar) → **Run workflow** button → **Run workflow**.
   Click into the run after a minute to see its logs.

## Step 5 — deploy the backend to Render (free, web service only)

1. [render.com](https://render.com) → sign up (GitHub sign-in is fine) → **New** → **Blueprint**.
2. Pick your repository. Render reads `render.yaml` and shows **one** web service (no cron job,
   so there's no payment prompt this time).
3. Fill in the env vars it asks for:
   - `GROQ_API_KEY`, `NEWSDATA_API_KEY`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`
   - `DATABASE_URL` — the **same** Neon connection string from Step 3
   - `CORS_ORIGINS` — leave as `http://localhost:5173` for now
4. Deploy. You'll get a URL like `https://ai-news-agent-api.onrender.com`.

## Step 6 — deploy the frontend (optional, free)

1. [vercel.com](https://vercel.com) → sign up with GitHub → **New Project** → pick the repo →
   set **Root Directory** to `frontend`.
2. Add env var `VITE_API_BASE` = your Render URL from Step 5.
3. Deploy → you get a URL like `https://your-app.vercel.app`.
4. Back on Render → your web service → Environment → update `CORS_ORIGINS` to that Vercel URL.

## Verifying it worked

- Backend: `curl https://your-backend.onrender.com/api/health` → `"config_problems": []`.
- Scheduler: GitHub → **Actions** tab → the most recent "Daily news digest" run → check its logs
  for `scheduled_run_finished`.
- Email: check the inbox of whichever address was set in **My Topics → Daily email digest**.

## Multiple people (you + a couple of others)

Each person signs into the app with their own name, sets their own topics, and sets their own
email under **My Topics**. GitHub Actions emails each person their own personalized digest every
morning — no extra setup per person.
