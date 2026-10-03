"""Pure text/URL helpers used for validation and de-duplication."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING = {"fbclid", "gclid", "ref", "cmp", "mc_cid", "mc_eid", "igshid", "ocid"}
_SUFFIX = re.compile(r"\s+[\-|–—:]\s+[^\-|–—:]{2,40}$")
_STOP = {
    "the", "and", "for", "with", "that", "this", "from", "into", "over", "after", "amid",
    "says", "said", "will", "has", "have", "are", "was", "were", "its", "his", "her", "new",
    "how", "why", "what", "who", "you", "your", "not", "but", "can", "may", "more", "than",
}


def normalize_url(url: str) -> str:
    p = urlsplit(url.strip())
    host = p.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    query = [
        (k, v) for k, v in parse_qsl(p.query, keep_blank_values=False)
        if not k.lower().startswith("utm_") and k.lower() not in _TRACKING
    ]
    return urlunsplit(("https", host, p.path.rstrip("/"), urlencode(sorted(query)), ""))


def url_hash(url: str) -> str:
    return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()


def normalize_title(title: str) -> str:
    t = unicodedata.normalize("NFKC", title).strip()
    if len(t.split()) >= 5:
        t = _SUFFIX.sub("", t)  # drop trailing " - Publisher"
    t = re.sub(r"[^\w\s]", " ", t.lower())
    return re.sub(r"\s+", " ", t).strip()


def title_tokens(norm_title: str) -> set[str]:
    return {w for w in norm_title.split() if len(w) > 2 and w not in _STOP}


def titles_similar(a: str, b: str, threshold: float = 0.85) -> bool:
    """True if two *normalized* titles likely describe the same story."""
    if not a or not b:
        return False
    if a == b:
        return True
    if SequenceMatcher(None, a, b).ratio() >= threshold:
        return True
    ta, tb = title_tokens(a), title_tokens(b)
    if len(ta) >= 4 and len(tb) >= 4:
        return len(ta & tb) / len(ta | tb) >= 0.7
    return False


def truncate(text: str | None, limit: int) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
