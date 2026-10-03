"""Step 1: the smallest possible LangGraph + Groq agent.

    python -m app.basic_agent "quantum computing"
"""
from __future__ import annotations

import sys
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.config.settings import ConfigError, get_settings
from app.services.groq_service import GroqService, LLMError


class BasicState(TypedDict, total=False):
    topic: str
    response: str


def build_basic_graph(llm: GroqService):
    def generate(state: BasicState) -> dict:
        text = llm.complete("You are a concise news analyst.",
                            f"Give a short, factual briefing on the news topic: {state['topic']}")
        return {"response": text}

    g = StateGraph(BasicState)
    g.add_node("generate", generate)
    g.add_edge(START, "generate")
    g.add_edge("generate", END)
    return g.compile()


def main() -> None:
    settings = get_settings()
    try:
        settings.require_groq()
    except ConfigError as exc:
        sys.exit(f"Error: {exc}")
    topic = " ".join(sys.argv[1:]).strip() or input("Topic: ").strip()
    if not topic:
        sys.exit("Please provide a topic.")
    llm = GroqService(settings.groq_api_key, settings.groq_model, timeout=settings.llm_timeout)
    try:
        print(build_basic_graph(llm).invoke({"topic": topic})["response"])
    except LLMError as exc:
        sys.exit(f"Error: {exc}")


if __name__ == "__main__":
    main()
