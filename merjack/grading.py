"""Visual grading — turn a metric into a 0..1 "goodness" and a red→amber→green color.

Pure functions (no Streamlit), so the "is this good for *this* buy-box?" logic is
testable. The UI maps each panel's value through these to a color. Example the user
asked for: a 1.5x multiple against a 3x target grades ~1.0 (green); 3x grades ~0 (red).
"""

from __future__ import annotations

# Anchors for a red -> amber -> green gradient.
_RED = (211, 47, 47)
_AMBER = (249, 168, 37)
_GREEN = (46, 125, 50)


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def color_rgb(goodness: float) -> tuple[int, int, int]:
    g = _clamp(goodness)
    return _lerp(_RED, _AMBER, g / 0.5) if g < 0.5 else _lerp(_AMBER, _GREEN, (g - 0.5) / 0.5)


def color_hex(goodness: float) -> str:
    r, g, b = color_rgb(goodness)
    return f"#{r:02x}{g:02x}{b:02x}"


def tint(goodness: float, alpha: float = 0.16) -> str:
    r, g, b = color_rgb(goodness)
    return f"rgba({r},{g},{b},{alpha})"


def _luminance(rgb) -> float:
    r, g, b = (c / 255 for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def text_on(goodness: float) -> str:
    """Accessible text color for a solid swatch of this color (dark on amber, white on red/green)."""
    return "#16130f" if _luminance(color_rgb(goodness)) > 0.6 else "#ffffff"


def label_for(goodness: float) -> str:
    g = goodness
    if g >= 0.75:
        return "Strong"
    if g >= 0.5:
        return "Good"
    if g >= 0.3:
        return "Fair"
    return "Weak"


# --- metric-specific grades (0 = bad/red, 1 = good/green) ------------------ #
def grade_score(score_0_100: float) -> float:
    """A composite/percentage score straight to 0..1."""
    return _clamp((score_0_100 or 0) / 100.0)


def _grade_under_threshold(ratio: float) -> float:
    """For 'lower is better vs a max'. ratio = value/max: comfortably under -> green,
    at the max -> borderline amber (~0.45), 1.5x over -> red."""
    if ratio <= 1.0:
        return _clamp(0.45 + (1.0 - ratio) / 0.5 * 0.55)  # at the max -> .45, half the max -> green
    return _clamp(0.45 - (ratio - 1.0) / 0.5 * 0.45)       # 1.5x the max -> red


def grade_multiple(multiple, target) -> float:
    """Lower multiple is better. Under your max -> green, at it -> borderline, over -> red."""
    if multiple is None:
        return 0.5
    target = target if target and target > 0 else 3.0
    return _grade_under_threshold(multiple / target)


def grade_at_least(value, target) -> float:
    """Higher is better (e.g. cash flow vs minimum). At target -> mid; well above -> green."""
    if value is None:
        return 0.5
    if not target or target <= 0:
        return 1.0 if value > 0 else 0.5
    return _clamp((value / target - 0.6) / 0.8)


def grade_at_most(value, target) -> float:
    """Lower is better (e.g. asking price vs max). Under -> green, at max -> borderline, over -> red."""
    if value is None:
        return 0.5
    if not target or target <= 0:
        return 0.5
    return _grade_under_threshold(value / target)


def grade_resale(multiple, lo: float = 2.0, hi: float = 5.0) -> float:
    """For a RESALE/exit multiple, **higher is better** (more profit) — the opposite of
    ``grade_multiple`` (which is for the buy multiple, lower-is-better)."""
    if multiple is None:
        return 0.5
    return _clamp((multiple - lo) / (hi - lo))


def grade_net(net, sde) -> float:
    """Net cash flow after debt, as a fraction of SDE. <=0 -> red; ~0.6+ -> green."""
    if net is None:
        return 0.0
    if not sde or sde <= 0:
        return _clamp(net / 300_000)
    return _clamp(net / sde)
