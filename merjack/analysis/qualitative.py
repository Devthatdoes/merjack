"""LLM qualitative scoring — the soft half of the rubric.

Turns a listing's free-text + descriptors into structured ``QualScore`` sub-scores
(recession resistance, recurring revenue, owner independence, stability, business-
vs-job) using LangChain's ``with_structured_output`` so the model must return data
matching our Pydantic schema.

The model is injected (``model=...``) for testability — pass a fake in tests, or let
it default to the configured cheap scoring model at runtime.
"""

from __future__ import annotations

import json
import re

from ..models import Listing, QualScore

SYSTEM = """You are an expert small-business acquisition analyst. You evaluate \
business-for-sale listings the way a buyer who wants a self-running, recession-\
resistant cash-flow business (to hold or flip) would.

Score the listing on each dimension from 0 to 100:
- recession_resistance: Is it a needed/non-discretionary service or product that \
people must pay for regardless of the economy? Higher = more essential.
- recurring_revenue: Are there repeat/contract customers and sticky demand vs. \
one-off transactions? Higher = stickier.
- owner_independence: Can it run WITHOUT the current owner (employees, managers, \
scheduling systems in place)? Higher = more absentee/turnkey.
- stability: Track record, years established, systems and staff in place. Higher = \
more proven and durable.
- business_not_job: Is the buyer acquiring a business (delegable) rather than buying \
themselves a full-time job? Higher = more of a real, delegable business.

Be skeptical of broker fluff. Base scores on concrete signals in the text. List any \
red flags (owner is the business, customer concentration, declining industry, \
discretionary product, missing financials, etc.). Keep the rationale to 2-4 sentences."""


def _format_listing(listing: Listing) -> str:
    def fmt(v, money=False):
        if v is None:
            return "unknown"
        return f"${v:,.0f}" if money else str(v)

    return "\n".join(
        [
            f"Title: {listing.title}",
            f"Industry: {fmt(listing.industry)}",
            f"Location: {fmt(listing.location)} ({fmt(listing.state)})",
            f"Asking price: {fmt(listing.asking_price, money=True)}",
            f"Cash flow (SDE): {fmt(listing.cash_flow_sde, money=True)}",
            f"Revenue: {fmt(listing.revenue, money=True)}",
            f"EBITDA: {fmt(listing.ebitda, money=True)}",
            f"Year established: {fmt(listing.year_established)}",
            f"Employees: {fmt(listing.employees)}",
            f"Home-based: {fmt(listing.home_based)}",
            f"Reason for selling: {fmt(listing.reason_for_selling)}",
            "",
            "Description:",
            listing.description or "(none provided)",
        ]
    )


FALLBACK_INSTRUCTION = (
    "Respond with ONLY a single JSON object — no prose, no markdown, no code fences. "
    "Keys: recession_resistance, recurring_revenue, owner_independence, stability, "
    "business_not_job (each an integer 0-100), rationale (short string), and "
    "red_flags (list of strings)."
)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _text_of(resp) -> str:
    """Extract plain text from a chat response (handles str or content-block list)."""
    content = getattr(resp, "content", resp)
    if isinstance(content, list):
        return " ".join(
            (b.get("text", "") if isinstance(b, dict) else str(b)) for b in content
        )
    return str(content)


def _parse_qualscore(text: str) -> QualScore:
    match = _JSON_RE.search(text)
    if not match:
        raise ValueError("no JSON object found in model output")
    return QualScore.model_validate(json.loads(match.group(0)))


def _structured(model):
    """Prefer tool/function calling — the most portable path across OpenRouter free
    models *and* Claude. Falls back to the default if a model doesn't accept method=."""
    try:
        return model.with_structured_output(QualScore, method="function_calling")
    except TypeError:
        return model.with_structured_output(QualScore)


def score_listing(listing: Listing, model=None) -> QualScore:
    """Return a ``QualScore`` for one listing.

    Strategy: native structured output via function calling first (strong models),
    then a plain-call + JSON-extraction fallback for weaker free models that ignore
    structured-output requests and emit prose. ``model`` defaults to the configured
    scoring model; a test fake can be injected.
    """
    if model is None:
        from ..llm import get_model

        model = get_model("scoring")

    messages = [("system", SYSTEM), ("human", _format_listing(listing))]
    try:
        result = _structured(model).invoke(messages)
        if result is not None:  # function_calling returns None when no tool call is emitted
            return result
    except Exception:  # noqa: BLE001 — fall through to prose-tolerant parsing
        pass
    # Fallback: plain call + JSON extraction (weak free models that ignore tools/schema).
    resp = model.invoke(messages + [("human", FALLBACK_INSTRUCTION)])
    return _parse_qualscore(_text_of(resp))


def score_many(listings: list[Listing], model=None) -> dict[str, QualScore]:
    """Score a batch, returning ``{listing.url: QualScore}``. Failures are skipped
    so one bad listing never kills the run."""
    out: dict[str, QualScore] = {}
    for listing in listings:
        try:
            out[listing.url] = score_listing(listing, model=model)
        except Exception:  # noqa: BLE001 — resilience over strictness during a run
            continue
    return out
