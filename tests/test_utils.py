from app.utils.text import normalize_title, normalize_url, titles_similar, url_hash


def test_normalize_url_strips_tracking_and_www():
    a = normalize_url("http://www.Example.com/story/?utm_source=x&id=5#frag")
    b = normalize_url("https://example.com/story?id=5")
    assert a == b and url_hash("http://www.example.com/story/?utm_medium=z&id=5") == url_hash(b)


def test_normalize_title_removes_publisher_suffix():
    assert normalize_title("OpenAI launches new model today - The Guardian") == "openai launches new model today"


def test_similar_titles_across_outlets():
    a = normalize_title("OpenAI launches GPT-6 model with big reasoning gains")
    b = normalize_title("OpenAI launches new GPT-6 model with major reasoning gains")
    assert titles_similar(a, b)
    assert not titles_similar(a, normalize_title("Cricket: India beat Australia in Test"))
