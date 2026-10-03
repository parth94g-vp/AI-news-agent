from app.assistant.news_assistant import NewsAssistant, heuristic_plan
from app.pipeline import run_pipeline
from tests.conftest import FakeLLM
from tests.test_graph import LISTING


def test_heuristic_plan_detects_topics():
    p = heuristic_plan("Show me today's cybersecurity news")
    assert "Cybersecurity" in p.topics
    assert heuristic_plan("Compare the major AI stories").intent == "compare"


def test_assistant_answers_from_db_with_sources(repo, user_id, make_deps, settings):
    deps, _ = make_deps(LISTING)
    run_pipeline(user_id, deps)
    llm = FakeLLM()
    res = NewsAssistant(repo, llm, settings).answer("Which stories are related to OpenAI?", user_id)
    assert res.sources and "OpenAI" in res.sources[0].title
    assert "ANSWER" in llm.calls


def test_assistant_no_matches_skips_llm(repo, user_id, settings):
    llm = FakeLLM()
    res = NewsAssistant(repo, llm, settings).answer("What happened in AI today?", user_id)
    assert res.sources == [] and "ANSWER" not in llm.calls


def test_assistant_survives_llm_failure(repo, user_id, make_deps, settings):
    deps, _ = make_deps(LISTING)
    run_pipeline(user_id, deps)
    res = NewsAssistant(repo, FakeLLM(fail=True), settings).answer("Tell me about OpenAI", user_id)
    assert "unavailable" in res.answer and res.sources
