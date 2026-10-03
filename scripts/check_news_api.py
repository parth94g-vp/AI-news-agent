"""Diagnose FreeNewsAPI: prints the raw HTTP status/body for a few request variants.

    python scripts/check_news_api.py
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config.settings import get_settings  # noqa: E402

s = get_settings()
if not s.news_api_key:
    sys.exit("FREENEWSAPI_API_KEY is not set in .env")
since = (datetime.now(timezone.utc) - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
variants = {
    "1. minimal (in_title + language)": {"in_title": "artificial intelligence", "language": "en"},
    "2. + page_size": {"in_title": "artificial intelligence", "language": "en", "page_size": 8},
    "3. + published_after": {"in_title": "artificial intelligence", "language": "en", "published_after": since},
    "4. all three": {"in_title": "artificial intelligence", "language": "en", "page_size": 8, "published_after": since},
}
for name, params in variants.items():
    try:
        r = requests.get(f"{s.news_api_base_url}/v1/news", params=params,
                         headers={"x-api-key": s.news_api_key}, timeout=20)
        print(f"{name}\n   HTTP {r.status_code}: {r.text[:220]!r}\n")
    except requests.RequestException as exc:
        print(f"{name}\n   network error: {exc}\n")
