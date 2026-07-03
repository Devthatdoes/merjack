"""Deal explanations tailored to the user's experience level.

Two layers, matching the project's deterministic-core / LLM-layer pattern:
  * summarize_deal: deterministic, template-based, proficiency-aware. Always available,
    no API key needed. Used as the quick read and as the fallback.
  * explain_deal:   an LLM-written narrative when a model is available, tailored to the
    user's level. Falls back to summarize_deal on any error.

``_deal_facts`` and ``_text_of`` are shared with the deal chat (merjack/chat.py).
"""

from __future__ import annotations

from typing import Optional

from ..config import SBA
from ..models import DealScore, Proficiency, Profile


def _money(x) -> str:
    return "unknown" if x is None else f"${x:,.0f}"


def _resale_range(deal: DealScore) -> Optional[str]:
    flips = deal.finance.flips
    lows = [s.multiple_low for s in flips if s.multiple_low is not None]
    highs = [s.multiple_high for s in flips if s.multiple_high is not None]
    if lows and highs:
        return f"{min(lows):.1f} to {max(highs):.1f}x"
    return None


def _clean(text: str) -> str:
    """Strip the punctuation that flags model output as AI: dash variants and curly quotes.
    Models ignore a 'no em dashes' instruction often enough that we enforce it here."""
    for ch in ("—", "–", "‒", "‑", "―"):  # em/en/figure/nb/horizontal dashes
        text = text.replace(ch, "-")
    return (text.replace("’", "'").replace("‘", "'")
                .replace("“", '"').replace("”", '"'))


def _text_of(resp) -> str:
    """Pull cleaned plain text from a chat response (string or content-block list)."""
    content = getattr(resp, "content", resp)
    if isinstance(content, list):
        text = " ".join((b.get("text", "") if isinstance(b, dict) else str(b)) for b in content)
    else:
        text = str(content)
    return _clean(text).strip()


# --------------------------------------------------------------------------- #
# Deterministic summary (always available)
# --------------------------------------------------------------------------- #
def summarize_deal(deal: DealScore, profile: Profile) -> str:
    f, l = deal.finance, deal.listing
    level = profile.proficiency
    mult = f"{f.multiple:.2f}x" if f.multiple else "an unknown multiple"
    takehome = _money(f.monthly_owner_income) if f.monthly_owner_income is not None else None
    resale = _resale_range(deal)
    risks = deal.red_flags

    if level == Proficiency.expert:
        parts = [f"Score {deal.composite:.0f}.", f"Buy {mult}."]
        if takehome:
            parts.append(f"About {takehome}/mo net after debt.")
        parts.append(f"Fit {deal.buybox_fit:.0f}%.")
        parts.append("No major risks." if not risks else f"Risks: {'; '.join(risks)}.")
        if resale:
            parts.append(f"Resale est. {resale}.")
        return " ".join(parts)

    if level == Proficiency.intermediate:
        s = f"Scores {deal.composite:.0f} out of 100 for your buy-box. Buy at {mult}"
        if takehome:
            s += f", with about {takehome} a month take-home after the loan"
        s += ". "
        s += "No major risks stood out. " if not risks else f"Watch: {'; '.join(risks)}. "
        if resale:
            s += f"Estimated resale {resale}."
        return s.strip()

    # novice
    verdict = "strong" if deal.composite >= 70 else "mixed" if deal.composite >= 45 else "weak"
    s = f"This looks {verdict} for your buy-box, scoring {deal.composite:.0f} out of 100. "
    if f.multiple:
        s += (f"You would pay {mult}, which means the price is about {f.multiple:.1f} times "
              f"what the business earns in a year. ")
    if takehome:
        s += f"After a typical SBA loan, you would keep around {takehome} a month. "
    s += "Nothing major stood out as a risk. " if not risks else f"The main things to check: {'; '.join(risks)}. "
    if resale:
        s += f"If you later sold it, a rough estimate is {resale} of yearly earnings."
    return s.strip()


# --------------------------------------------------------------------------- #
# LLM narrative (on demand)
# --------------------------------------------------------------------------- #
_LEVEL = {
    Proficiency.novice: (
        "The reader is new to buying businesses. Explain in plain language and define any "
        "term the first time you use it (SDE, multiple, SBA loan, DSCR). Be encouraging but honest."
    ),
    Proficiency.intermediate: (
        "The reader knows the basics. Be concise and skip definitions of common terms."
    ),
    Proficiency.expert: (
        "The reader is experienced. Lead with the bottom line, be terse, and skip all hand-holding."
    ),
}

_BASE_SYSTEM = (
    "You are a business-acquisition analyst. Give a short, honest verdict on ONE specific deal "
    "using only the facts provided plus general acquisition knowledge. Cover whether the price and "
    "cash flow work, the main risks, and what to verify in due diligence. Write in plain professional "
    "English. Do not use em dashes. Do not invent numbers. Keep it under 180 words."
)


def _deal_facts(deal: DealScore) -> str:
    f, q, l = deal.finance, deal.qualitative, deal.listing
    lines = [
        f"Title: {l.title}",
        f"Industry: {l.industry or 'unknown'}",
        f"Location: {l.location or l.state or 'unknown'}",
        f"Year established: {l.year_established or 'unknown'}",
        f"Asking price: {_money(l.asking_price)}",
        f"Cash flow (SDE): {_money(l.cash_flow_sde)}",
        f"Multiple: {f.multiple:.2f}x" if f.multiple else "Multiple: unknown",
        f"Estimated take-home after the loan: {_money(f.monthly_owner_income)}/mo, "
        f"{_money(f.net_cash_flow_after_debt)}/yr",
        f"Buy-box fit: {deal.buybox_fit:.0f}%",
        f"Composite score: {deal.composite:.0f}/100",
    ]
    if f.down_payment is not None:
        lines.append(
            f"Financing (estimated): 10% down = {_money(f.down_payment)}, loan {_money(f.loan_amount)} "
            f"at about {SBA.annual_rate * 100:.1f}% SBA over {SBA.term_years} years; "
            f"debt service {_money(f.annual_debt_service)}/yr ({_money(f.monthly_debt_service)}/mo)"
        )
    resale = _resale_range(deal)
    if resale:
        lines.append(f"Estimated resale multiple: {resale}")
    if q is not None:
        lines.append(
            f"Quality scores (0-100): recession resistance {q.recession_resistance}, "
            f"recurring revenue {q.recurring_revenue}, owner independence {q.owner_independence}, "
            f"stability {q.stability}, business-not-job {q.business_not_job}"
        )
        if q.rationale:
            lines.append(f"Quality notes: {q.rationale}")
    lines.append("Risk flags: " + ("; ".join(deal.red_flags) if deal.red_flags else "none"))
    if l.description:
        lines.append(f"Listing description: {l.description}")
    return "\n".join(lines)


def explain_deal(deal: DealScore, profile: Profile, model=None) -> str:
    """LLM verdict tailored to the user's level. Falls back to ``summarize_deal``."""
    system = f"{_BASE_SYSTEM}\n\n{_LEVEL[profile.proficiency]}"
    if model is None:
        try:
            from ..llm import get_model

            model = get_model("explain")
        except Exception:  # noqa: BLE001
            return summarize_deal(deal, profile)
    try:
        resp = model.invoke([("system", system), ("human", _deal_facts(deal))])
        return _text_of(resp) or summarize_deal(deal, profile)
    except Exception:  # noqa: BLE001
        return summarize_deal(deal, profile)
