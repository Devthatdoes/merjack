"""Merjack, local Streamlit UI.

Run with:  .venv/bin/streamlit run app.py

Set a buy-box, load listings, and rank them. Every panel is colored by how well it
fits the criteria you set. Sourcing here is the manual importer; live sourcing comes
later.
"""

from __future__ import annotations

import csv
import html
import io
import json
import random

import streamlit as st

from merjack import config, keys, llm
from merjack.glossary import GLOSSARY
from merjack.analysis.explain import explain_deal, summarize_deal
from merjack.chat import answer as chat_answer
from merjack.grading import (
    color_hex,
    grade_at_least,
    grade_at_most,
    grade_multiple,
    grade_net,
    grade_resale,
    grade_score,
    label_for,
    text_on,
    tint,
)
from merjack.graph import run_pipeline
from merjack.industries import INDUSTRY_OPTIONS
from merjack.models import BuyBox, OwnerInvolvement, Proficiency, Profile, Strategy
from merjack.sample_data import generate_listings
from merjack.sources import ManualSource
from merjack.storage import load_profile, save_profile

st.set_page_config(page_title="Merjack", page_icon="📊", layout="wide")

SAMPLE_ROWS = [
    {"title": "Reliable Home Inspection", "url": "sample/1", "state": "NY", "industry": "home inspection",
     "price": "1800000", "cash_flow": "617000", "established": "1994", "employees": "6",
     "description": "30-yr firm; 5 inspectors do the work, owner schedules; realtor referral base; retiring."},
    {"title": "Printing & Promo Center", "url": "sample/2", "state": "NY", "industry": "printing",
     "price": "600000", "cash_flow": "310000", "established": "2006", "employees": "3",
     "description": "Storefront print shop; walk-in plus repeat small-business orders; owner runs counter."},
    {"title": "GreenScape Lawn Care", "url": "sample/3", "state": "NY", "industry": "landscaping",
     "price": "950000", "cash_flow": "340000", "established": "2011", "employees": "9",
     "description": "Recurring monthly maintenance contracts; 2 crews plus a manager; owner does sales only."},
    {"title": "Trendy Boutique", "url": "sample/4", "state": "CA", "industry": "retail",
     "price": "2000000", "cash_flow": "300000", "established": "2024", "employees": "4",
     "description": "Fashion boutique; owner is the buyer and face of the brand; discretionary; 1 yr old."},
]

TEMPLATE_CSV = (
    "title,url,state,industry,price,cash_flow,revenue,established,employees,description\n"
    "Example HVAC Co,https://bizbuysell.com/listing/123,NY,hvac,900000,350000,1800000,2008,8,"
    "Recurring maintenance contracts; manager runs daily ops; owner absentee.\n"
)

STRATEGY_LABELS = {"hold": "Hold for cash flow", "quick_flip": "Quick flip", "scale_flip": "Scale and flip"}
PROFICIENCY_CAPTION = {
    "novice": "Terms are explained throughout.",
    "intermediate": "Some terms explained.",
    "expert": "Minimal explanations.",
}

STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Hanken+Grotesk:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap');

:root{ --paper:#FBF8F2; --raised:#fff; --ink:#16130F; --muted:#5C5346; --line:#E7E0D4; }

html, body, .stApp{ background:var(--paper); color:var(--ink);
  font-family:'Hanken Grotesk', system-ui, sans-serif; }
[data-testid="stHeader"]{ background:transparent; }
[data-testid="stToolbar"]{ display:none; }
.block-container{ padding-top:2.2rem; max-width:1160px; }

h1,h2,h3,h4{ font-family:'Fraunces', Georgia, serif; color:var(--ink);
  letter-spacing:-.012em; font-weight:600; }
h1{ font-size:2.5rem; line-height:1.04; }
h2{ font-size:1.4rem; } h3{ font-size:1.2rem; }
[data-testid="stSidebar"]{ background:#F4EFE6; border-right:1px solid var(--line); }
[data-testid="stSidebar"] h1{ font-size:1.5rem; }

.merjack-mono{ font-family:'Space Mono', monospace; font-variant-numeric:tabular-nums; }
.merjack-hero{ margin:.1rem 0 1.2rem; }
.merjack-hero h1{ margin:.1rem 0 .35rem; }
.merjack-hero p{ color:var(--muted); font-size:1.02rem; max-width:62ch; margin:0; }

.merjack-deal{ border:1px solid var(--line); border-left:6px solid; border-radius:12px;
  padding:14px 18px; margin:10px 0; background:var(--raised);
  transition:transform .16s ease, box-shadow .16s ease;
  animation:merjack-rise .42s cubic-bezier(.2,.7,.2,1) both; }
.merjack-deal:hover{ transform:translateY(-2px); box-shadow:0 10px 26px rgba(20,19,15,.08); }
.merjack-deal-top{ display:flex; align-items:center; justify-content:space-between; gap:12px; }
.merjack-deal-title{ font-family:'Fraunces',serif; font-size:1.18rem; font-weight:600; }
.merjack-deal-sub{ color:var(--muted); font-weight:400; font-size:.85rem;
  font-family:'Hanken Grotesk',sans-serif; }
.merjack-deal-chips{ display:flex; gap:8px; flex-wrap:wrap; margin-top:10px; align-items:center; }
@keyframes merjack-rise{ from{opacity:0; transform:translateY(10px);} to{opacity:1; transform:translateY(0);} }

.merjack-pill{ border-radius:999px; padding:5px 13px; font-family:'Space Mono',monospace;
  font-weight:700; font-size:.92rem; white-space:nowrap; }
.merjack-chip{ border-radius:999px; padding:3px 11px; font-size:.78rem; font-weight:600;
  border:1px solid; white-space:nowrap; }
.merjack-flag{ color:#a4161a; font-weight:600; }

.merjack-cards{ display:flex; gap:10px; flex-wrap:wrap; margin:6px 0 12px; }
.merjack-card{ flex:1; min-width:150px; border-left:4px solid; border-radius:9px; padding:11px 14px; }
.merjack-card-neutral{ background:#F4EFE6; border-color:var(--line); }
.merjack-card-label{ font-size:.64rem; letter-spacing:.10em; text-transform:uppercase;
  color:var(--muted); font-weight:700; }
.merjack-card-value{ font-family:'Space Mono',monospace; font-variant-numeric:tabular-nums;
  font-size:1.26rem; font-weight:700; color:var(--ink); margin-top:3px; }

.stButton>button{ border-radius:9px; font-weight:600; }
[data-testid="stBaseButton-primary"]{ background:var(--ink); color:var(--paper); border:none; }
[data-testid="stBaseButton-primary"]:hover{ background:#2a2620; color:#fff; }
</style>
"""


# --------------------------------------------------------------------------- #
# Render helpers
# --------------------------------------------------------------------------- #
def money(x) -> str:
    return "—" if x is None else f"${x:,.0f}"


def inject_css():
    st.markdown(STYLE, unsafe_allow_html=True)


def score_pill(score: float) -> str:
    g = grade_score(score)
    return f"<span class='merjack-pill' style='background:{color_hex(g)};color:{text_on(g)}'>{score:.0f}%</span>"


def chip(label: str, value: str, goodness: float) -> str:
    c = color_hex(goodness)
    return (f"<span class='merjack-chip' style='color:{c};border-color:{c};background:{tint(goodness, 0.16)}'>"
            f"{label} <span class='merjack-mono'>{value}</span></span>")


def card(label: str, value: str, goodness: float) -> str:
    return (f"<div class='merjack-card' style='background:{tint(goodness)};border-color:{color_hex(goodness)}'>"
            f"<div class='merjack-card-label'>{label}</div>"
            f"<div class='merjack-card-value'>{value}</div></div>")


def card_neutral(label: str, value: str) -> str:
    return (f"<div class='merjack-card merjack-card-neutral'>"
            f"<div class='merjack-card-label'>{label}</div>"
            f"<div class='merjack-card-value'>{value}</div></div>")


def flip_card(fl) -> str:
    g = grade_resale(fl.target_multiple)
    profit = fl.projected_profit
    sign = "+" if profit >= 0 else "-"
    pcolor = "#2e7d32" if profit >= 0 else "#a4161a"
    name = fl.name.replace("_", " ").title()
    rng = f" ({fl.multiple_low:.1f}-{fl.multiple_high:.1f}x)" if fl.multiple_low is not None else ""
    basis = " · ".join(fl.breakdown) if fl.breakdown else ""
    return (
        f"<div class='merjack-card' style='background:{tint(g)};border-color:{color_hex(g)}'>"
        f"<div class='merjack-card-label'>{name}, sell at {fl.target_multiple:.2f}x{rng}</div>"
        f"<div class='merjack-card-value'>{money(fl.projected_sale_price)}</div>"
        f"<div class='merjack-mono' style='font-size:.8rem;font-weight:700;color:{pcolor};margin-top:2px;'>"
        f"{sign}{money(abs(profit))} profit</div>"
        + (f"<div style='font-size:.66rem;color:#6b7280;margin-top:4px;'>{basis}</div>" if basis else "")
        + "</div>"
    )


def wrap_cards(cards_html) -> str:
    return f"<div class='merjack-cards'>{''.join(cards_html)}</div>"


def cards_row(items) -> str:
    return wrap_cards([card(l, v, g) for l, v, g in items])


def deal_list_card(d, buybox, idx: int = 0) -> str:
    f, l = d.finance, d.listing
    g = grade_score(d.composite)
    chips = (
        chip("Multiple", f"{f.multiple:.2f}x" if f.multiple else "—", grade_multiple(f.multiple, buybox.max_multiple))
        + chip("Est. net/yr", money(f.net_cash_flow_after_debt), grade_net(f.net_cash_flow_after_debt, l.cash_flow_sde))
        + chip("Fit", f"{d.buybox_fit:.0f}%", d.buybox_fit / 100)
    )
    n = len(d.red_flags)
    flags = (f"<span class='merjack-flag'>{n} risk{'s' if n != 1 else ''}</span>"
             if n else "<span style='color:#2e7d32;font-weight:600'>no risks</span>")
    return (
        f"<div class='merjack-deal' style='border-left-color:{color_hex(g)};animation-delay:{idx * 0.05:.2f}s'>"
        f"<div class='merjack-deal-top'><div class='merjack-deal-title'>{html.escape(l.title)}"
        f"<span class='merjack-deal-sub'> · {html.escape(l.state or '—')} · {html.escape(l.industry or '—')}</span></div>"
        f"{score_pill(d.composite)}</div>"
        f"<div class='merjack-deal-chips'>{chips}<span style='margin-left:auto'>{flags}</span></div></div>"
    )


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
def render_settings():
    """Model tier, per-task model overrides, and API keys."""
    with st.sidebar.expander("Settings", expanded=False):
        tiers = list(config.TIERS.keys())
        tier = st.radio(
            "Model tier", tiers, index=tiers.index(st.session_state.get("tier", config.TIER)),
            format_func=lambda t: config.TIERS[t]["label"],
        )
        st.session_state["tier"] = tier

        presets = config.TIERS[tier]["models"]
        st.caption("Models used for each task.")
        overrides = {}
        for task in ("scoring", "explain", "sourcing"):
            key = f"model_{task}_{tier}"
            if key not in st.session_state:
                st.session_state[key] = presets[task]
            overrides[task] = st.text_input(task, key=key)

        st.divider()
        st.caption("API keys, stored on this machine.")
        for provider in ("anthropic", "openai", "openrouter"):
            status = "set" if keys.has_api_key(provider) else "not set"
            val = st.text_input(f"{provider} ({status})", type="password",
                                key=f"key_{provider}", placeholder="paste to add or update")
            if st.button(f"Save {provider} key", key=f"save_{provider}"):
                if val.strip():
                    keys.save_api_key(provider, val.strip())
                    st.success(f"Saved {provider} key")
                    st.rerun()
                else:
                    st.warning("Enter a key first")
        return tier, overrides["scoring"]


def sidebar():
    st.sidebar.title("Merjack")
    st.sidebar.caption("Find businesses worth buying.")
    _, scoring_model_id = render_settings()
    st.sidebar.divider()

    current = st.session_state.get("profile") or load_profile()
    levels = [p.value for p in Proficiency]
    choice = st.sidebar.selectbox("Experience level", levels, index=levels.index(current.proficiency.value))
    st.sidebar.caption(PROFICIENCY_CAPTION[choice])
    profile = Profile(proficiency=Proficiency(choice))
    if profile != current:
        save_profile(profile)
        st.session_state["profile"] = profile

    st.sidebar.divider()
    st.sidebar.subheader("Buy-box")
    st.sidebar.caption("Leave any field blank to ignore it.")
    state = st.sidebar.text_input("State", placeholder="Any state").strip().upper() or None
    max_price = st.sidebar.number_input("Max asking price", value=None, step=50_000, placeholder="No limit")
    min_cf = st.sidebar.number_input("Minimum cash flow (SDE)", value=None, step=25_000, placeholder="No minimum")
    max_mult = st.sidebar.number_input("Max multiple", value=None, step=0.5, placeholder="No limit")
    industries = st.sidebar.multiselect("Industries", INDUSTRY_OPTIONS, default=[])
    strat_values = [s.value for s in Strategy]
    strategy = st.sidebar.selectbox(
        "Plan after buying", strat_values, index=strat_values.index("quick_flip"),
        format_func=lambda s: STRATEGY_LABELS[s],
    )
    buybox = BuyBox(
        state=state, max_asking_price=max_price, min_cash_flow=min_cf, max_multiple=max_mult,
        industries=industries, owner_involvement=OwnerInvolvement.any, strategy=Strategy(strategy),
    )

    st.sidebar.divider()
    use_qual = st.sidebar.checkbox(
        "Add quality analysis", value=False,
        help="Rates softer factors like recurring revenue and how much the business depends on its owner. Adds time.",
    )
    use_market = st.sidebar.checkbox(
        "Add market analysis (web)", value=False,
        help="Searches the web for local demand and typical sale multiples in the listing's industry and "
             "area, and folds that into the resale estimate. Needs a SearXNG instance. Slower.",
    )
    limit = st.sidebar.number_input("Deals to analyze", min_value=1, value=25, step=5)
    return profile, buybox, use_qual, use_market, int(limit), scoring_model_id


# --------------------------------------------------------------------------- #
# Source input
# --------------------------------------------------------------------------- #
def rows_from_csv_text(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def get_source():
    st.subheader("1 · Load listings")
    mode = st.radio("Source", ["Sample data", "Random data", "Paste CSV", "Upload file"], horizontal=True)

    if mode == "Sample data":
        st.caption("Four example listings.")
        return ManualSource.from_rows(SAMPLE_ROWS)

    if mode == "Random data":
        c1, c2 = st.columns([3, 1])
        n = c1.slider("Number of listings", 4, 40, 12)
        if c2.button("Regenerate"):
            st.session_state["gen_seed"] = random.randint(1, 999_999)
        seed = st.session_state.setdefault("gen_seed", 7)
        st.caption("Generated listings with a mix of strong and weak deals. Regenerate for a new set.")
        return ManualSource.from_rows(generate_listings(n, seed=seed))

    if mode == "Paste CSV":
        st.download_button("Download CSV template", TEMPLATE_CSV, "merjack_listings_template.csv",
                           "text/csv", key="tmpl_paste")
        st.caption("Paste rows from a real listing. Columns: title, price, cash_flow, state, industry, description.")
        text = st.text_area("Paste CSV", height=150,
                            placeholder="title,price,cash_flow,state,industry\nAcme Plumbing,900000,350000,TX,plumbing")
        if text.strip():
            try:
                return ManualSource.from_rows(rows_from_csv_text(text))
            except Exception as e:  # noqa: BLE001
                st.error(f"Could not read that CSV: {e}")
        return None

    st.download_button("Download CSV template", TEMPLATE_CSV, "merjack_listings_template.csv",
                       "text/csv", key="tmpl_upload")
    st.caption("Upload a CSV or JSON file of listings.")
    upload = st.file_uploader("Upload a file", type=["csv", "json"])
    if upload is not None:
        raw = upload.getvalue().decode("utf-8")
        try:
            if upload.name.endswith(".json"):
                payload = json.loads(raw)
                rows = payload.get("listings", payload) if isinstance(payload, dict) else payload
            else:
                rows = rows_from_csv_text(raw)
            return ManualSource.from_rows(rows)
        except Exception as e:  # noqa: BLE001
            st.error(f"Could not read that file: {e}")
    return None


# --------------------------------------------------------------------------- #
# Results + deal detail
# --------------------------------------------------------------------------- #
def show_results(ranked, buybox, profile):
    st.subheader(f"2 · Ranked deals ({len(ranked)})")
    for i, d in enumerate(ranked):
        st.markdown(deal_list_card(d, buybox, i), unsafe_allow_html=True)

    st.divider()
    st.subheader("3 · Deal detail")
    idx = st.selectbox(
        "Choose a deal", range(len(ranked)),
        format_func=lambda i: f"{ranked[i].composite:.0f}% · {ranked[i].listing.title}",
    )
    deal_detail(ranked[idx], buybox, profile)


def resale_section(f, buybox):
    quick = next((s for s in f.flips if s.name == "quick_flip"), None)
    scale = next((s for s in f.flips if s.name == "scale_flip"), None)

    if buybox.strategy == Strategy.hold:
        st.markdown("**Resale potential**")
        st.caption("You picked hold for cash flow, so the yearly income above is what matters most.")
        return

    show = [quick] if buybox.strategy == Strategy.quick_flip else [quick, scale]
    show = [s for s in show if s]
    if not show:
        return

    st.markdown("**Resale potential**")
    if f.multiple:
        lows = [s.multiple_low for s in show if s.multiple_low is not None]
        highs = [s.multiple_high for s in show if s.multiple_high is not None]
        rng = f"{min(lows):.1f} to {max(highs):.1f}x" if lows and highs else "—"
        st.markdown(
            f"<p style='margin:.1rem 0 .4rem;color:var(--muted);'>Buy at "
            f"<b class='merjack-mono' style='color:var(--ink)'>{f.multiple:.2f}x</b>, resell around "
            f"<b class='merjack-mono' style='color:var(--ink)'>{rng}</b> "
            f"<span style='font-size:.8rem;'>(estimate)</span></p>",
            unsafe_allow_html=True,
        )
    st.markdown(wrap_cards([flip_card(s) for s in show]), unsafe_allow_html=True)


def deal_detail(d, buybox, profile):
    f, q, l = d.finance, d.qualitative, d.listing
    g = grade_score(d.composite)
    sub = " · ".join(p for p in [
        html.escape(l.industry) if l.industry else None,
        html.escape(l.location or l.state) if (l.location or l.state) else None,
        f"established {l.year_established}" if l.year_established else None,
        f"{l.employees} employees" if l.employees else None,
    ] if p)
    st.markdown(
        f"<h3 style='margin-bottom:.1rem;'>{html.escape(l.title)} &nbsp; {score_pill(d.composite)} "
        f"<span style='color:{color_hex(g)};font-weight:700;font-size:1rem;'>{label_for(g)}</span></h3>"
        f"<div style='color:var(--muted);font-size:.95rem;margin-bottom:.7rem;'>{sub}</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"<div style='font-size:1.02rem;margin:.1rem 0 1rem;'>{summarize_deal(d, profile)}</div>",
        unsafe_allow_html=True,
    )

    # The number a buyer actually cares about: monthly take-home after the loan.
    if f.monthly_owner_income is not None:
        tg = grade_net(f.net_cash_flow_after_debt, l.cash_flow_sde)
        st.markdown(
            "<div style='margin:.1rem 0 1.1rem;'>"
            "<div style='font-size:.68rem;text-transform:uppercase;letter-spacing:.08em;"
            "color:var(--muted);font-weight:700;'>Estimated owner take-home after the loan</div>"
            f"<span class='merjack-mono' style='font-size:1.85rem;font-weight:700;color:{color_hex(tg)};'>"
            f"{money(f.monthly_owner_income)}/mo</span>"
            f"<span class='merjack-mono' style='font-size:1.05rem;color:var(--muted);margin-left:12px;'>"
            f"{money(f.net_cash_flow_after_debt)}/yr</span></div>",
            unsafe_allow_html=True,
        )

    st.markdown("**Snapshot**")
    st.markdown(cards_row([
        ("Asking", money(l.asking_price), grade_at_most(l.asking_price, buybox.max_asking_price)),
        ("Cash flow (SDE)", money(l.cash_flow_sde), grade_at_least(l.cash_flow_sde, buybox.min_cash_flow)),
        ("Multiple", f"{f.multiple:.2f}x" if f.multiple else "—", grade_multiple(f.multiple, buybox.max_multiple)),
        ("Buy-box fit", f"{d.buybox_fit:.0f}%", d.buybox_fit / 100),
    ]), unsafe_allow_html=True)

    st.markdown("**Financing (SBA, 10% down)**")
    monthly_sde = (l.cash_flow_sde / 12) if l.cash_flow_sde else None
    st.markdown(wrap_cards([
        card_neutral("Down payment", money(f.down_payment)),
        card_neutral("Loan amount", money(f.loan_amount)),
        card_neutral("Cash flow / mo", money(monthly_sde)),
        card_neutral("Est. loan payment / mo", money(f.monthly_debt_service)),
    ]), unsafe_allow_html=True)
    st.caption(
        f"Loan payment and take-home are estimated at a {config.SBA.annual_rate * 100:.1f}% SBA rate "
        f"over {config.SBA.term_years} years. Your actual rate will vary."
    )

    if f.flips:
        resale_section(f, buybox)

    if q is not None:
        st.markdown("**Quality assessment**")
        st.caption("Estimated by the model from the listing details, scored 0 to 100.")
        st.markdown(cards_row([
            ("Recession-resist", str(q.recession_resistance), grade_score(q.recession_resistance)),
            ("Recurring rev", str(q.recurring_revenue), grade_score(q.recurring_revenue)),
            ("Owner-independent", str(q.owner_independence), grade_score(q.owner_independence)),
            ("Stability", str(q.stability), grade_score(q.stability)),
            ("Business not job", str(q.business_not_job), grade_score(q.business_not_job)),
        ]), unsafe_allow_html=True)
        if q.rationale:
            st.info(q.rationale)

    if d.red_flags:
        st.markdown("**Risks**")
        for flag in d.red_flags:
            st.markdown(f"<div class='merjack-flag'>{flag}</div>", unsafe_allow_html=True)
    else:
        st.success("No major risks found.")

    st.markdown("**In-depth explanation**")
    explain_key = f"explain_{l.url}"
    if st.button("Explain this deal", key=f"explainbtn_{l.url}"):
        with st.spinner("Writing the explanation"):
            st.session_state[explain_key] = explain_deal(d, profile)
    if st.session_state.get(explain_key):
        st.write(st.session_state[explain_key])

    st.markdown("**Ask about this deal**")
    chat_key = f"chat_{l.url}"
    history = st.session_state.setdefault(chat_key, [])
    for role, content in history:
        with st.chat_message(role):
            st.write(content)
    prompt = st.chat_input("Ask a question about this deal")
    if prompt:
        history.append(("user", prompt))
        with st.chat_message("user"):
            st.write(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Thinking"):
                try:
                    reply = chat_answer(d, profile, history[:-1], prompt)
                except Exception:  # noqa: BLE001
                    reply = "Sorry, I could not reach the model right now. Try again in a moment."
            st.write(reply)
        history.append(("assistant", reply))

    if l.description:
        with st.expander("Listing description"):
            st.write(l.description)

    if profile.proficiency != Proficiency.expert:
        with st.expander("Key terms", expanded=profile.proficiency == Proficiency.novice):
            for term, definition in GLOSSARY.items():
                st.markdown(f"**{term}** {definition}")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    inject_css()
    profile, buybox, use_qual, use_market, limit, scoring_model_id = sidebar()

    st.markdown(
        "<div class='merjack-hero'><h1>Find your next business</h1>"
        "<p>Compare listings against your criteria and rank the strongest deals.</p></div>",
        unsafe_allow_html=True,
    )

    source = get_source()
    if st.button("Find deals", type="primary", disabled=source is None):
        with st.spinner("Scoring and ranking"):
            try:
                model = llm.build_model(scoring_model_id) if use_qual else None
                ranked = run_pipeline(source, buybox, profile, limit=limit,
                                      use_qualitative=use_qual, use_market=use_market, model=model)
                st.session_state["ranked"] = ranked
                st.session_state["ranked_buybox"] = buybox
            except Exception as e:  # noqa: BLE001
                st.error(f"Run failed: {type(e).__name__}: {e}")

    if st.session_state.get("ranked"):
        st.divider()
        show_results(st.session_state["ranked"], st.session_state.get("ranked_buybox", buybox), profile)


if __name__ == "__main__":
    main()
