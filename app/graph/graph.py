"""LangGraph wiring.

START -> discover_news -> validate -> deduplicate -> check_cache -> classify (title-based)
      -> relevance -> fetch_content (bodies only for relevant articles) -> summarize -> rank
      -> digest -> persist -> END

Conditional edges short-circuit to END whenever a stage leaves no articles (e.g. the
news API is down), so later stages never run on empty input.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from langgraph.graph import END, START, StateGraph

from app.config.settings import Settings
from app.database.repositories import NewsRepository
from app.graph.nodes.check_cache import check_cache
from app.graph.nodes.classify_topics import classify_topics
from app.graph.nodes.deduplicate import deduplicate
from app.graph.nodes.digest import generate_digest
from app.graph.nodes.discover_news import discover_news
from app.graph.nodes.fetch_content import fetch_content
from app.graph.nodes.persist import persist_digest
from app.graph.nodes.rank import rank_articles
from app.graph.nodes.relevance import calculate_relevance
from app.graph.nodes.summarize import summarize_articles
from app.graph.nodes.validate_articles import validate_articles
from app.graph.state import NewsState
from app.services.groq_service import LLMClient
from app.services.news_api import NewsProvider


@dataclass
class Dependencies:
    provider: NewsProvider
    llm: LLMClient
    repo: NewsRepository
    settings: Settings


def _continue_if_articles(state: NewsState) -> str:
    return "continue" if state.get("articles") else "end"


def build_graph(deps: Dependencies):
    s, p, llm, repo = deps.settings, deps.provider, deps.llm, deps.repo
    g = StateGraph(NewsState)
    nodes: list[tuple[str, Callable[[NewsState], dict]]] = [
        ("discover_news", lambda st: discover_news(st, provider=p, settings=s)),
        ("validate_articles", lambda st: validate_articles(st, settings=s)),
        ("deduplicate", lambda st: deduplicate(st, settings=s)),
        ("check_cache", lambda st: check_cache(st, repo=repo)),
        ("classify_topics", lambda st: classify_topics(st, llm=llm)),
        ("calculate_relevance", lambda st: calculate_relevance(st, settings=s)),
        ("fetch_content", lambda st: fetch_content(st, provider=p, settings=s)),
        ("summarize_articles", lambda st: summarize_articles(st, llm=llm, settings=s)),
        ("rank_articles", lambda st: rank_articles(st)),
        ("generate_digest", lambda st: generate_digest(st, llm=llm, settings=s)),
        ("persist_digest", lambda st: persist_digest(st, repo=repo)),
    ]
    for name, fn in nodes:
        g.add_node(name, fn)
    g.add_edge(START, "discover_news")
    guarded = {"discover_news", "validate_articles", "deduplicate", "fetch_content", "classify_topics", "calculate_relevance"}
    for (name, _), (nxt, _) in zip(nodes, nodes[1:]):
        if name in guarded:
            g.add_conditional_edges(name, _continue_if_articles, {"continue": nxt, "end": END})
        else:
            g.add_edge(name, nxt)
    g.add_edge(nodes[-1][0], END)
    return g.compile()
