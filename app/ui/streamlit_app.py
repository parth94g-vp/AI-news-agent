"""Streamlit dashboard.  Run:  streamlit run app/ui/streamlit_app.py"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # allow `streamlit run` from anywhere

import streamlit as st  # noqa: E402

from app.bootstrap import Services, build_services  # noqa: E402
from app.pipeline import run_pipeline  # noqa: E402
from app.schemas import ArticleView  # noqa: E402
from app.taxonomy import TAXONOMY  # noqa: E402
from app.utils.timeutils import format_local, local_today  # noqa: E402

st.set_page_config(page_title="AI News Agent", page_icon="📰", layout="wide")


@st.cache_resource(show_spinner=False)
def services() -> Services:
    return build_services()


svc = services()
repo, tz = svc.repo, svc.settings.timezone


# ------------------------------------------------------------------ callbacks
def cb_toggle_save(user_id: int, article_id: int) -> None:
    repo.toggle_saved(user_id, article_id)


def cb_feedback(user_id: int, article_id: int, key: str) -> None:
    choice = st.session_state.get(f"fbr_{key}")
    if choice:
        repo.set_feedback(user_id, article_id, 1 if choice.startswith("👍") else -1,
                          st.session_state.get(f"fbc_{key}"))
        st.toast("Thanks for the feedback!")


def render_article(a: ArticleView, user_id: int, ctx: str) -> None:
    key = f"{ctx}_{a.id}"
    with st.container(border=True):
        left, right = st.columns([5, 1]) if a.image_url else (st.container(), None)
        with left:
            st.markdown(f"#### [{a.title}]({a.url})")
            meta = [a.source, format_local(a.published_at, tz)]
            if a.topic:
                meta.append(f"{a.topic} › {a.subtopic}")
            if a.relevance is not None:
                meta.append(f"relevance {a.relevance:.0%}")
            st.caption(" · ".join(meta))
            st.write(a.summary or "_No summary available._")
        if right is not None:
            right.image(a.image_url, use_container_width=True)
        c1, c2, c3 = st.columns([1, 1, 4])
        c1.button("★ Saved" if a.saved else "☆ Save", key=f"save_{key}", on_click=cb_toggle_save,
                  args=(user_id, a.id), type="primary" if a.saved else "secondary")
        c2.link_button("Read full ↗", a.url)
        with c3.popover("Feedback" + (" 👍" if a.feedback == 1 else " 👎" if a.feedback == -1 else "")):
            st.radio("Was this summary helpful?", ["👍 Helpful", "👎 Not helpful"], key=f"fbr_{key}",
                     index=None if a.feedback is None else (0 if a.feedback == 1 else 1))
            st.text_input("Comment (optional)", key=f"fbc_{key}")
            st.button("Submit", key=f"fbs_{key}", on_click=cb_feedback, args=(user_id, a.id, key))


# -------------------------------------------------------------------- sidebar
st.sidebar.title("📰 AI News Agent")
for problem in svc.config_problems:
    st.sidebar.error(problem)

with st.sidebar.form("login"):
    name = st.text_input("Your name", value=st.session_state.get("username", ""))
    if st.form_submit_button("Sign in / create profile"):
        try:
            uid, uname = repo.create_or_get_user(name)
            st.session_state.update(user_id=uid, username=uname)
        except ValueError as exc:
            st.sidebar.error(str(exc))

user_id = st.session_state.get("user_id")
if user_id is None:
    st.title("Welcome 👋")
    st.info("Enter a name in the sidebar to create your personalized news profile.")
    st.stop()

st.sidebar.success(f"Signed in as **{st.session_state['username']}**")
saved_prefs = repo.get_preferences(user_id)

with st.sidebar.expander("🎯 My topics", expanded=not saved_prefs):
    chosen: dict[str, list[str]] = {}
    for topic, subs in TAXONOMY.items():
        chosen[topic] = st.multiselect(topic, list(subs), default=saved_prefs.get(topic, []), key=f"pref_{topic}")
    if st.button("Save preferences", type="primary"):
        try:
            repo.set_preferences(user_id, chosen)
            st.success("Preferences saved.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

if st.sidebar.button("🔄 Refresh my news", disabled=svc.deps is None or not saved_prefs, use_container_width=True):
    with st.spinner("Discovering, filtering and summarizing today's news… (can take a minute or two)"):
        try:
            result = run_pipeline(user_id, svc.deps)
            st.session_state["last_run"] = result
        except Exception as exc:  # noqa: BLE001
            st.sidebar.error(f"Refresh failed: {exc}")
if not saved_prefs:
    st.sidebar.caption("Pick at least one subtopic to enable refresh.")

last = st.session_state.get("last_run")
if last:
    with st.sidebar.expander("Last run details"):
        st.json({"saved": last.saved_count, **last.stats})
        for err in last.errors[:15]:
            st.warning(err)

# ----------------------------------------------------------------------- tabs
tab_news, tab_saved, tab_chat = st.tabs(["📰 Today's News", "🔖 Saved", "🤖 Ask the News"])

with tab_news:
    digest = repo.get_digest(user_id)
    if digest is None:
        st.info("No news yet. Choose your topics in the sidebar, then click **Refresh my news**.")
    else:
        stale = digest.digest_date != local_today(tz)
        st.title(f"Your news for {digest.digest_date:%A, %d %B %Y}")
        if stale:
            st.warning("This digest is not from today. Click **Refresh my news** for the latest.")
        if digest.overview:
            st.info(digest.overview)
        for topic in TAXONOMY:
            topic_entries = [e for e in digest.entries if e.topic == topic]
            if not topic_entries:
                continue
            st.header(topic)
            for sub in TAXONOMY[topic]:
                group = [e for e in topic_entries if e.subtopic == sub]
                if group:
                    st.subheader(sub)
                    for art in group:
                        render_article(art, user_id, "d")

with tab_saved:
    saved = repo.list_saved(user_id)
    if not saved:
        st.info("Articles you bookmark will appear here.")
    for art in saved:
        render_article(art, user_id, "s")

with tab_chat:
    st.caption("Answers come from the news collected in your database, with numbered sources.")
    history = st.session_state.setdefault("chat", [])
    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            for i, src in enumerate(msg.get("sources", []), 1):
                st.markdown(f"[{i}] [{src['title']}]({src['url']}) — {src['source']}")
    if svc.assistant is None:
        st.warning("Add your API keys to .env to enable the assistant.")
    elif question := st.chat_input("e.g. What happened in AI today?"):
        history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            try:
                with st.spinner("Searching today's news…"):
                    res = svc.assistant.answer(question, user_id)
                st.markdown(res.answer)
                srcs = [{"title": s.title, "url": s.url, "source": s.source} for s in res.sources]
                for i, s in enumerate(srcs, 1):
                    st.markdown(f"[{i}] [{s['title']}]({s['url']}) — {s['source']}")
                history.append({"role": "assistant", "content": res.answer, "sources": srcs})
            except ValueError as exc:
                st.warning(str(exc))
