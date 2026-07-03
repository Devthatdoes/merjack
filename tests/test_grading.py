"""Grading -> color logic. Pure, no UI."""

from merjack.grading import (
    color_hex,
    grade_at_least,
    grade_at_most,
    grade_multiple,
    grade_net,
    grade_score,
    label_for,
    text_on,
)


def test_text_on_is_accessible():
    assert text_on(0.5) == "#16130f"   # dark text on amber (white would fail contrast)
    assert text_on(1.0) == "#ffffff"   # white on green
    assert text_on(0.0) == "#ffffff"   # white on red


def test_color_endpoints_and_midpoint():
    assert color_hex(0.0) == "#d32f2f"   # red
    assert color_hex(1.0) == "#2e7d32"   # green
    assert color_hex(0.5) == "#f9a825"   # amber
    # clamps out-of-range
    assert color_hex(-1) == "#d32f2f"
    assert color_hex(2) == "#2e7d32"


def test_grade_multiple_user_example():
    # Under your max should read green; at the max is borderline (NOT red); over is red.
    assert grade_multiple(1.5, 3.0) == 1.0            # well under the max -> green
    assert grade_multiple(2.5, 3.0) > 0.55            # still under the max -> greenish, not red
    assert 0.35 < grade_multiple(3.0, 3.0) < 0.55     # at the max -> borderline amber
    assert grade_multiple(4.5, 3.0) < 0.2             # well over the max -> red


def test_grade_at_least_cashflow():
    assert grade_at_least(617_000, 300_000) == 1.0   # well above min -> green
    assert grade_at_least(150_000, 300_000) == 0.0   # well below -> red
    assert 0.3 < grade_at_least(300_000, 300_000) < 0.7  # at min -> mid


def test_grade_at_most_price():
    assert grade_at_most(600_000, 2_000_000) == 1.0          # cheap vs max -> green
    assert grade_at_most(1_400_000, 2_000_000) > 0.55        # under the cap -> greenish
    assert 0.35 < grade_at_most(2_000_000, 2_000_000) < 0.55  # at the cap -> borderline


def test_grade_net():
    assert grade_net(8_540, 300_000) < 0.1             # almost nothing left -> red
    assert grade_net(354_686, 617_000) > 0.5           # healthy -> green-ish
    assert grade_net(-5_000, 617_000) == 0.0


def test_grade_resale_higher_is_better():
    from merjack.grading import grade_resale
    # Opposite direction from the buy multiple: higher resale = greener.
    assert grade_resale(5.0) > grade_resale(3.5) > grade_resale(2.0)
    assert grade_resale(2.0) == 0.0
    assert grade_resale(5.0) == 1.0


def test_grade_score_and_labels():
    assert grade_score(90) == 0.9
    assert label_for(0.9) == "Strong"
    assert label_for(0.1) == "Weak"
    assert label_for(0.6) == "Good"
