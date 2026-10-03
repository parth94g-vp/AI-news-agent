# Personalized AI News Agent

LangGraph + LangChain + Groq (`llama-3.3-70b-versatile`) + FreeNewsAPI + SQLite/SQLAlchemy + Streamlit.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# put your keys in .env  (GROQ_API_KEY and NEWSDATA_API_KEY, or FREENEWSAPI_API_KEY)
python -m app.basic_agent "quantum computing"           # Step 1 sanity check (LangGraph + Groq)
streamlit run app/ui/streamlit_app.py                   # full app
pytest                                                  # 33 tests, no network needed
```
Keys: https://console.groq.com (Groq) and https://www.freenewsapi.io/user/register.php (news).

Using the app: sign in with a name → pick topics in **My topics** → **Refresh my news** (1-2 min the first time) →
read the digest, ☆ save, give feedback, or ask questions in **Ask the News**.

## Pipeline (`app/graph/`)
```
discover_news → validate → deduplicate → check_cache → classify → relevance → fetch_content → summarize → rank → digest → persist
```
Stages that leave no articles short-circuit to END. Every node is wrapped by `safe_node`: an exception becomes an entry in
`state["errors"]` instead of crashing the run.

| Node | In | Processing | Out (state update) |
|---|---|---|---|
| discover_news | preferences | one provider search per selected subtopic; a failing query is logged, others continue | `articles` (metadata only) |
| validate_articles | articles | drop junk titles and stale items | `articles` |
| deduplicate | articles | URL, normalized title, fuzzy/Jaccard title match (same story, different outlet) | `articles` |
| check_cache | articles | swap in articles already summarized in SQLite (`cached=True`) | `articles` |
| classify_topics | articles | batched (10/call) LLM classification on titles; falls back to the discovery hint if the LLM fails | `articles` + topic/subtopic |
| calculate_relevance | articles, prefs | heuristic score (no LLM); below `RELEVANCE_THRESHOLD` → dropped | `articles` |
| fetch_content | articles | provider *details* call for uncached, relevant articles only; re-dedupe by URL | `articles` + body/url |
| summarize_articles | articles | one LLM call per uncached article (capped); extractive fallback on failure | `articles` + summary/importance |
| rank_articles | articles | `0.5·relevance + 0.3·importance + 0.2·recency` | sorted `articles` |
| generate_digest | articles | top-N per subtopic + optional LLM overview | `digest` |
| persist_digest | articles, digest | one SQLite transaction | `saved_count` |

State (`app/graph/state.py`): `articles` is replaced by each node, `errors` accumulates (`operator.add`), `stats` is merged.

**LLM-call savings:** duplicates, off-topic and irrelevant articles are removed before any body fetch or summary; cached articles
are never re-classified or re-summarized; fallback (non-AI) summaries are not cached so they get retried next run.

## Layout
`services/news_api.py` is the only file that knows FreeNewsAPI. Implement `NewsProvider` (`search`, `fetch_content`) to swap providers.
`database/` (SQLAlchemy models + repository returning DTOs) never imports LLM code; `ui/` only talks to the repository/pipeline.
Change `DATABASE_URL` to move to PostgreSQL later. Scheduling/email/WhatsApp are deliberately not implemented; `run_pipeline(user_id, deps)`
in `app/pipeline.py` is the single entry point a future scheduler would call.

## FreeNewsAPI notes
* Free tier: 5,000 requests/day, 2 req/s (the client throttles, retries 429s using `Retry-After`, and times out at 15 s).
* `/v1/news` returns only uuid/title/time/publisher; body + original URL come from `/v1/details`, hence the separate `fetch_content` node.
* The search text is sent as `in_title` (the provider removed `q`). Request parameters `language`, `country`, `published_after`, `order_by` follow the provider's public docs; if the provider's
  contract changes, only `app/services/news_api.py` needs editing. Set `FREENEWSAPI_ORDER_BY` / `NEWS_COUNTRY` in `.env` if you want them.

## Also in this repo
- **React UI + FastAPI backend** — see `README_REACT.md`
- **Scheduler (daily auto-refresh) + email digest + trending topics** — see `README_DEPLOY.md`
