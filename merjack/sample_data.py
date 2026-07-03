"""Sample + randomly-generated listings for testing the pipeline without live data.

``generate_listings(n, seed)`` produces a realistic spread — recession-resistant
blue-collar service businesses at sane multiples (good deals) mixed with pricey,
young, discretionary businesses (weak deals) — so ranking, red flags, and the
color grading all get exercised. Deterministic given a seed.
"""

from __future__ import annotations

import random

# Each industry carries traits the description + scoring will reflect.
GOOD = [
    dict(name="hvac", suffix="HVAC Services", recurring=True, essential=True),
    dict(name="plumbing", suffix="Plumbing", recurring=False, essential=True),
    dict(name="electrical", suffix="Electric", recurring=False, essential=True),
    dict(name="landscaping", suffix="Lawn & Landscape", recurring=True, essential=False),
    dict(name="commercial cleaning", suffix="Commercial Cleaning", recurring=True, essential=True),
    dict(name="pest control", suffix="Pest Control", recurring=True, essential=True),
    dict(name="auto repair", suffix="Auto Repair", recurring=False, essential=True),
    dict(name="roofing", suffix="Roofing", recurring=False, essential=True),
    dict(name="pool service", suffix="Pool Service", recurring=True, essential=False),
    dict(name="home inspection", suffix="Home Inspection", recurring=False, essential=True),
    dict(name="septic service", suffix="Septic Service", recurring=True, essential=True),
    dict(name="self storage", suffix="Self Storage", recurring=True, essential=False),
]
WEAK = [
    dict(name="retail boutique", suffix="Boutique", recurring=False, essential=False),
    dict(name="specialty coffee", suffix="Coffee House", recurring=False, essential=False),
    dict(name="restaurant", suffix="Bistro", recurring=False, essential=False),
    dict(name="gift shop", suffix="Gift Shop", recurring=False, essential=False),
    dict(name="boutique fitness", suffix="Fitness Studio", recurring=True, essential=False),
    dict(name="event planning", suffix="Events Co.", recurring=False, essential=False),
]

PREFIXES = [
    "Summit", "Cedar Valley", "Allstar", "Premier", "Reliable", "Metro", "Coastal",
    "Riverside", "Liberty", "Apex", "Heritage", "Blue Sky", "Greenline", "Hometown",
    "Precision", "Guardian", "Evergreen", "Pioneer", "Sunrise", "Anchor", "Ironclad",
]
STATES = ["NY", "NJ", "PA", "FL", "TX", "CA", "OH", "GA", "NC", "IL", "AZ", "MA", "CO", "WA", "MI", "TN"]
REASONS = ["retirement", "relocating out of state", "health reasons", "pursuing other ventures", "partnership buyout"]

_OWNER_TEXT = {
    "absentee": "A general manager and crews run daily operations; the owner is largely absentee.",
    "semi": "The owner handles estimates and sales; staff run the field work.",
    "dependent": "The owner is hands-on and central to daily operations.",
}


def _describe(ind: dict, owner_role: str, year: int, rng: random.Random) -> str:
    return " ".join([
        "Recurring service contracts and repeat accounts." if ind["recurring"]
        else "Mostly project / transactional work.",
        "Essential, non-discretionary service." if ind["essential"]
        else "Discretionary / lifestyle spend, sensitive to the economy.",
        _OWNER_TEXT[owner_role],
        f"Established {year}.",
        f"Reason for selling: {rng.choice(REASONS)}.",
    ])


def generate_listings(n: int = 12, seed: int | None = None) -> list[dict]:
    """Return ``n`` randomized listing rows (same shape ManualSource accepts)."""
    rng = random.Random(seed)
    rows: list[dict] = []
    for i in range(n):
        weak = rng.random() < 0.35
        ind = rng.choice(WEAK if weak else GOOD)

        cash = rng.randrange(250_000, 900_001, 5_000)
        if weak:
            mult = round(rng.uniform(3.2, 6.5), 1)
            year = rng.randint(2015, 2024)
            owner = rng.choices(["dependent", "semi"], weights=[3, 1])[0]
        else:
            mult = round(rng.uniform(1.6, 3.6), 1)
            year = rng.randint(1985, 2017)
            owner = rng.choices(["absentee", "semi"], weights=[2, 1])[0]

        asking = int(round(cash * mult / 1000) * 1000)
        employees = max(2, round(cash / 80_000) + rng.randint(-2, 3))
        rows.append({
            "title": f"{rng.choice(PREFIXES)} {ind['suffix']}",
            "url": f"gen://{rng.randrange(100000, 999999)}-{i}",
            "state": rng.choice(STATES),
            "industry": ind["name"],
            "price": str(asking),
            "cash_flow": str(cash),
            "established": str(year),
            "employees": str(employees),
            "description": _describe(ind, owner, year, rng),
        })
    return rows
