"""Topic / subtopic taxonomy. The first keyword of each subtopic is the search query
sent to the news provider; all keywords are used for relevance scoring."""
from __future__ import annotations

TAXONOMY: dict[str, dict[str, tuple[str, ...]]] = {
    "Technology": {
        "Artificial Intelligence": ("artificial intelligence", "AI", "OpenAI", "LLM", "machine learning", "chatbot"),
        "Software": ("software development", "programming", "open source", "developer", "app", "cloud"),
        "Cybersecurity": ("cybersecurity", "ransomware", "data breach", "hackers", "vulnerability", "malware"),
        "Startups": ("startup", "funding round", "venture capital", "founder", "seed round", "unicorn"),
        "Gadgets": ("smartphone", "laptop launch", "wearable", "gadget review", "chipset", "consumer electronics"),
    },
    "Business": {
        "Finance": ("finance", "banking", "interest rates", "inflation", "investment", "central bank"),
        "Markets": ("stock market", "Wall Street", "Sensex", "Nifty", "shares", "commodities"),
        "Companies": ("company earnings", "merger", "acquisition", "CEO", "IPO", "quarterly results"),
        "Economy": ("GDP growth", "unemployment rate", "economic policy", "trade deficit", "recession", "economy"),
    },
    "Science": {
        "Space": ("space", "NASA", "ISRO", "rocket", "satellite", "astronaut"),
        "Physics": ("physics", "quantum", "particle", "astrophysics", "physicists", "superconductor"),
        "Research": ("scientific study", "researchers", "discovery", "clinical trial", "peer-reviewed", "scientists"),
        "Environment": ("climate change", "global warming", "renewable energy", "wildlife conservation", "pollution", "sustainability"),
    },
    "Sports": {
        "Cricket": ("cricket", "IPL", "Test match", "ODI", "BCCI", "wicket"),
        "Football": ("football", "Premier League", "Champions League", "FIFA", "goal", "striker"),
        "Tennis": ("tennis", "Grand Slam", "Wimbledon", "ATP", "WTA", "US Open"),
        "Olympics": ("Olympics", "Olympic Games", "medal tally", "IOC", "Paralympics", "athlete"),
    },
    "Health": {
        "Medicine": ("medicine", "vaccine", "disease outbreak", "FDA approval", "treatment", "public health"),
        "Mental Health": ("mental health", "wellbeing", "therapy", "anxiety", "depression awareness", "mindfulness"),
        "Fitness & Nutrition": ("fitness", "nutrition study", "diet trend", "exercise research", "wellness", "healthy eating"),
    },
    "Entertainment": {
        "Movies": ("movie release", "box office", "film festival", "Hollywood", "Bollywood", "director"),
        "Music": ("music release", "album launch", "concert tour", "Grammy", "musician", "streaming chart"),
        "Television": ("TV series", "streaming show", "television network", "season finale", "renewal", "showrunner"),
        "Celebrities": ("celebrity news", "red carpet", "award show", "celebrity interview", "entertainment industry", "pop culture"),
    },
    "World": {
        "Politics": ("election", "government policy", "parliament", "president", "prime minister", "political party"),
        "International Relations": ("diplomacy", "summit", "trade agreement", "United Nations", "foreign policy", "sanctions"),
        "Conflict & Security": ("conflict", "military operation", "ceasefire", "security forces", "geopolitics", "defense"),
    },
    "Gaming": {
        "Video Games": ("video game release", "game studio", "gaming industry", "esports", "console launch", "game review"),
        "Esports": ("esports tournament", "esports team", "gaming championship", "esports player", "competitive gaming", "gaming league"),
    },
}

SUBTOPIC_TO_TOPIC: dict[str, str] = {sub: topic for topic, subs in TAXONOMY.items() for sub in subs}


def all_pairs() -> list[tuple[str, str]]:
    return [(t, s) for t, subs in TAXONOMY.items() for s in subs]


def validate_preferences(prefs: dict[str, list[str]]) -> dict[str, list[str]]:
    """Return cleaned prefs (deduped, taxonomy order). Raises ValueError on unknown names."""
    clean: dict[str, list[str]] = {}
    for topic, subs in prefs.items():
        if topic not in TAXONOMY:
            raise ValueError(f"Unknown topic: {topic!r}")
        for sub in subs:
            if sub not in TAXONOMY[topic]:
                raise ValueError(f"Unknown subtopic {sub!r} for topic {topic!r}")
        wanted = [s for s in TAXONOMY[topic] if s in set(subs)]
        if wanted:
            clean[topic] = wanted
    return clean


def taxonomy_prompt() -> str:
    return "\n".join(f"- {t} > {s}" for t, s in all_pairs())
