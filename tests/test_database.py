import pytest

from app.schemas import Digest, DigestSection, WorkingArticle
from app.utils.timeutils import utcnow
from tests.conftest import BODY


def art(uuid="u1", url="https://n.example/1", **kw):
    base = dict(external_id=uuid, title="OpenAI ships new model", url=url, content=BODY, source="Wire",
                published_at=utcnow(), topic="Technology", subtopic="Artificial Intelligence", confidence=0.9,
                relevance=0.9, summary="S", summary_source="ai", importance=0.8, rank_score=0.7)
    base.update(kw)
    return WorkingArticle(**base)


def test_user_and_preferences(repo):
    uid, _ = repo.create_or_get_user("bob")
    assert repo.create_or_get_user("bob")[0] == uid  # idempotent
    with pytest.raises(ValueError):
        repo.create_or_get_user("!")
    repo.set_preferences(uid, {"Technology": ["Software"], "Sports": ["Tennis", "Cricket"]})
    assert repo.get_preferences(uid) == {"Technology": ["Software"], "Sports": ["Cricket", "Tennis"]}
    with pytest.raises(ValueError):
        repo.set_preferences(uid, {"Technology": ["Nope"]})
    repo.set_preferences(uid, {"Sports": ["Tennis"]})  # replaces
    assert repo.get_preferences(uid) == {"Sports": ["Tennis"]}


def test_save_digest_prevents_duplicates_and_reads_back(repo, user_id):
    d = Digest(digest_date=utcnow().date(), overview="ov",
               sections=[DigestSection(topic="Technology", subtopic="Artificial Intelligence", article_keys=["u1"])])
    assert repo.save_digest(user_id, [art()], d) == 1
    # same article again under a different uuid but same URL -> still ONE article row
    assert repo.save_digest(user_id, [art(uuid="u1"), art(uuid="other")][:1], d) == 1
    view = repo.get_digest(user_id)
    assert len(view.entries) == 1 and view.overview == "ov"
    assert view.entries[0].topic == "Technology" and view.entries[0].summary == "S"


def test_cache_lookup_only_returns_ai_summaries(repo, user_id):
    d = Digest(digest_date=utcnow().date(), sections=[])
    repo.save_digest(user_id, [art(), art("u2", "https://n.example/2", summary_source="fallback")], d)
    cache = repo.find_cached(["u1", "u2"], [])
    assert "u1" in cache and "u2" not in cache and cache["u1"].cached


def test_bookmarks_and_feedback(repo, user_id):
    d = Digest(digest_date=utcnow().date(),
               sections=[DigestSection(topic="Technology", subtopic="Artificial Intelligence", article_keys=["u1"])])
    repo.save_digest(user_id, [art()], d)
    aid = repo.get_digest(user_id).entries[0].id
    assert repo.toggle_saved(user_id, aid) is True
    assert [a.id for a in repo.list_saved(user_id)] == [aid]
    repo.set_feedback(user_id, aid, -1, "meh")
    repo.set_feedback(user_id, aid, 1, "better")  # upsert
    e = repo.get_digest(user_id).entries[0]
    assert e.saved and e.feedback == 1
    assert repo.toggle_saved(user_id, aid) is False
    with pytest.raises(ValueError):
        repo.set_feedback(user_id, aid, 5)


def test_article_without_url_rolls_back(repo, user_id):
    d = Digest(digest_date=utcnow().date(), sections=[])
    with pytest.raises(ValueError):
        repo.save_digest(user_id, [art(), art("u9", None)], d)
    assert repo.find_cached(["u1"], []) == {}  # transaction rolled back as a whole


def test_email_validation_and_storage(repo, user_id):
    repo.set_email(user_id, "me@example.com")
    with pytest.raises(ValueError):
        repo.set_email(user_id, "not-an-email")
    repo.set_email(user_id, "")  # clears it
    with pytest.raises(ValueError):
        repo.set_email(999999, "x@y.com")


def test_list_users_with_preferences_only_includes_those_with_subtopics(repo):
    uid1, _ = repo.create_or_get_user("withprefs")
    repo.set_preferences(uid1, {"Technology": ["Software"]})
    repo.set_email(uid1, "a@b.com")
    uid2, _ = repo.create_or_get_user("noprefs")
    users = repo.list_users_with_preferences()
    ids = {u[0] for u in users}
    assert uid1 in ids and uid2 not in ids
    assert (uid1, "withprefs", "a@b.com") in users


def test_trending_detects_spike_vs_baseline(repo):
    from datetime import timedelta
    from sqlalchemy import update
    from app.database import models as m
    uid, _ = repo.create_or_get_user("trenduser")
    # 7 quiet days: 1 article/day in Cybersecurity
    for i in range(7, 0, -1):
        a = art(uuid=f"quiet{i}", url=f"https://n.example/quiet{i}", topic="Technology", subtopic="Cybersecurity")
        repo.save_digest(uid, [a], Digest(digest_date=utcnow().date(), sections=[]))
        with repo.session() as s:
            s.execute(update(m.Article).where(m.Article.external_id == f"quiet{i}")
                     .values(fetched_at=utcnow().replace(tzinfo=None) - timedelta(days=i)))
    # today: a spike of 5
    today_articles = [art(uuid=f"spike{i}", url=f"https://n.example/spike{i}",
                          topic="Technology", subtopic="Cybersecurity") for i in range(5)]
    repo.save_digest(uid, today_articles, Digest(digest_date=utcnow().date(), sections=[]))
    trending = repo.get_trending_subtopics(baseline_days=7, min_count=3, ratio_threshold=1.6)
    hit = next((t for t in trending if t.subtopic == "Cybersecurity"), None)
    assert hit is not None and hit.today_count == 5 and hit.baseline_avg == 1.0 and hit.ratio == 5.0


def test_trending_ignores_low_volume_subtopics(repo):
    uid, _ = repo.create_or_get_user("lowvol")
    repo.save_digest(uid, [art(uuid="only1", url="https://n.example/only1")],
                     Digest(digest_date=utcnow().date(), sections=[]))
    trending = repo.get_trending_subtopics(min_count=3)
    assert all(t.subtopic != "Artificial Intelligence" for t in trending)
