"""Streamlit UI smoke test via AppTest — runs app.py headless, no network."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def test_app_boots_without_error():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception


def test_app_finds_and_ranks_sample_deals():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    # Default source is the built-in sample set; click "Find & rank deals".
    button = next(b for b in at.button if "Find" in b.label)
    button.click().run()
    assert not at.exception
    ranked = at.session_state["ranked"]
    assert len(ranked) == 4
    # Best-first ordering, composites within range.
    assert ranked[0].composite >= ranked[-1].composite
    assert all(0 <= d.composite <= 100 for d in ranked)
