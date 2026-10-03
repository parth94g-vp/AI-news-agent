from app.graph.nodes.deduplicate import dedupe_articles
from app.graph.nodes.relevance import score_relevance
from app.pipeline import run_pipeline
from app.schemas import WorkingArticle
from tests.conftest import FakeLLM, listing_item

LISTING = [
    listing_item("a1", "OpenAI launches powerful new AI model for developers"),
    listing_item("a2", "OpenAI launches powerful new AI model for developers - Reuters"),   # duplicate story
    listing_item("a3", "Massive data breach exposes millions of customer records"),
    listing_item("a4", "Cricket: India win thrilling test match at Lord's"),                  # not selected topic
    listing_item("a5", "Local bakery wins award for best croissant in town"),                  # off taxonomy
    listing_item("a6", "AI", 1),                                                               # invalid title
]


def test_dedupe_by_similar_title():
    arts = [WorkingArticle(**a.model_dump()) for a in LISTING[:2]]
    assert len(dedupe_articles(arts)) == 1


def test_relevance_scoring(user_id):
    prefs = {"Technology": ["Artificial Intelligence"]}
    on = WorkingArticle(title="OpenAI AI model", topic="Technology", subtopic="Artificial Intelligence", confidence=0.9)
    off = WorkingArticle(title="Cricket final", topic="Sports", subtopic="Cricket", confidence=0.9)
    assert score_relevance(on, prefs) > 0.6 and score_relevance(off, prefs) == 0.0


def test_full_pipeline_end_to_end(repo, user_id, make_deps):
    deps, provider = make_deps(LISTING)
    res = run_pipeline(user_id, deps)
    view = repo.get_digest(user_id)
    titles = [e.title for e in view.entries]
    assert res.errors == [] and res.saved_count == 2
    assert any("OpenAI" in t for t in titles) and any("breach" in t for t in titles)
    assert not any("Cricket" in t or "bakery" in t for t in titles)
    assert view.overview == "Overview text."
    assert provider.detail_calls == 2  # dupes, junk and off-topic never hit the details endpoint
    assert deps.llm.calls.count("SUMMARIZE") == 2


def test_second_run_uses_cache_and_skips_llm(repo, user_id, make_deps):
    deps, provider = make_deps(LISTING)
    run_pipeline(user_id, deps)
    llm2 = FakeLLM()
    deps2, provider2 = make_deps(LISTING, llm=llm2)
    res = run_pipeline(user_id, deps2)
    assert res.stats["cache_hits"] == 2
    assert "SUMMARIZE" not in llm2.calls           # no repeated summaries
    assert llm2.calls.count("CLASSIFY") == 1       # only the not-yet-seen article(s)
    assert len(repo.get_digest(user_id).entries) == 2


def test_news_api_down_degrades_gracefully(repo, user_id, make_deps):
    deps, _ = make_deps(LISTING, fail_search=True)
    res = run_pipeline(user_id, deps)
    assert res.saved_count == 0 and any("discover_news" in e for e in res.errors)
    assert repo.get_digest(user_id) is None


def test_llm_down_uses_fallbacks(repo, user_id, make_deps):
    deps, _ = make_deps(LISTING, llm=FakeLLM(fail=True))
    res = run_pipeline(user_id, deps)
    entries = repo.get_digest(user_id).entries
    assert res.errors and len(entries) >= 1 and all(e.summary for e in entries)
    # fallback summaries are NOT cached as AI summaries
    assert repo.find_cached(["a1", "a3"], []) == {}


def test_requires_preferences(repo, make_deps):
    uid, _ = repo.create_or_get_user("nopref")
    deps, _ = make_deps(LISTING)
    import pytest
    with pytest.raises(ValueError):
        run_pipeline(uid, deps)
