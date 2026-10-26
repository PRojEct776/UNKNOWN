import pytest

from app.rag.reliability import compute_reliability, get_venue_quality


def _web_v(host):
    return get_venue_quality(host, origin="web", url="https://" + host + "/page")


@pytest.mark.parametrize(
    "host",
    [
        "jamaica-travel.com",
        "oracle.com",
        "explosionsafety.org",
        "acmeplumbing.com",
        "cellphonereviews.net",
        "computersciencehub.org",
        "webmd.com",
        "example.org",
    ],
)
def test_ordinary_sites_get_the_web_default(host):
    assert _web_v(host) == 0.50


@pytest.mark.parametrize(
    "host, expected",
    [
        ("nature.com", 1.00),
        ("go.nature.com", 1.00),
        ("link.springer.com", 0.80),
        ("ieeexplore.ieee.org", 0.85),
        ("dl.acm.org", 0.85),
        ("pnas.org", 0.95),
    ],
)
def test_known_publisher_domains_keep_their_quality(host, expected):
    assert _web_v(host) == expected


@pytest.mark.parametrize("host", ["notnature.com", "nature.com.evil.io", "fakeieee.org"])
def test_lookalike_domains_do_not_inherit_a_publisher_score(host):
    assert _web_v(host) == 0.50


def test_preprint_hosts_stay_preprints():
    assert _web_v("arxiv.org") == 0.40
    assert _web_v("www.biorxiv.org") == 0.40


def test_wikipedia_is_still_half():
    assert _web_v("en.wikipedia.org") == 0.50


def test_journal_names_still_use_the_substring_table():
    assert get_venue_quality("Nature", origin="web") == 1.00
    assert get_venue_quality("IEEE Access", origin="web") == 0.85
    assert get_venue_quality("Journal of Biology", origin="scholarly") == 0.75


def test_tavily_style_chunk_scores_below_a_real_publisher_page():
    base = {"year": None, "cites": 0, "origin": "web"}
    blog = compute_reliability({**base, "venue": "jamaica-travel.com", "url": "https://jamaica-travel.com/x"})
    paper = compute_reliability({**base, "venue": "nature.com", "url": "https://nature.com/x"})
    assert 0.0 <= blog < paper <= 1.0