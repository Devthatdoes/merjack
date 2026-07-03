import time
import os
from merjack.llm import get_model
from merjack.models import Listing, BuyBox, Profile, DealScore, FinanceResult, QualScore
from merjack.analysis.explain import explain_deal, summarize_deal
from merjack.analysis.market import assess_market
from merjack.analysis.qualitative import score_listing

def benchmark_task(name, task_fn, *args, **kwargs):
    print(f"Running benchmark: {name}...")
    start_time = time.perf_counter()
    result = task_fn(*args, **kwargs)
    end_time = time.perf_counter()
    duration = end_time - start_time
    
    # Basic sanity check to prevent false positives (e.g. empty results or defaults)
    if result is None or str(result).strip() == "":
        raise ValueError(f"Benchmark {name} returned an empty result. Possible false positive.")
    
    text_output = str(result)
    approx_tokens = len(text_output.split())
    tps = approx_tokens / duration if duration > 0 else 0
    print(f"  Duration: {duration:.4f}s")
    print(f"  Approx Tokens: {approx_tokens}")
    print(f"  Approx TPS: {tps:.2f}")
    return duration, tps

def run_all_benchmarks():
    listing = Listing(
        url="http://example.com/deal",
        title="Home Inspection Business",
        asking_price=1800000,
        cash_flow_sde=617000,
        location="Minnesota",
        state="MN",
        industry="Home Services",
        description="Highly profitable home inspection business with recurring revenue and strong systems."
    )
    profile = Profile(proficiency="intermediate")
    
    finance = FinanceResult(
        multiple=2.92, 
        down_payment=180000, 
        loan_amount=1620000, 
        monthly_debt_service=22000, 
        annual_debt_service=264000, 
        net_cash_flow_after_debt=353000, 
        monthly_owner_income=29416, 
        flips=[]
    )
    qual = QualScore(
        recession_resistance=80, 
        recurring_revenue=70, 
        owner_independence=90, 
        stability=85, 
        business_not_job=90, 
        rationale="Strong systems in place.", 
        red_flags=[]
    )
    deal = DealScore(
        listing=listing, 
        finance=finance, 
        qualitative=qual, 
        buybox_fit=100, 
        composite=85, 
        red_flags=[], 
        explanation=""
    )

    results = {}
    
    # Task 1: Qualitative Scoring
    results['scoring'] = benchmark_task("Qualitative Scoring", score_listing, listing)
    
    # Task 2: Explanation
    # To avoid false positives, we ensure the LLM version was actually used and not just the fallback
    # We can do this by comparing the result with the deterministic summary.
    duration, tps = benchmark_task("Deal Explanation", explain_deal, deal, profile)
    # We need to actually call the function again or capture result to compare
    res_explain = explain_deal(deal, profile)
    res_summary = summarize_deal(deal, profile)
    if res_explain == res_summary:
        print("  WARNING: Explanation result is identical to summary. Likely fallback used.")
    results['explain'] = (duration, tps)
    
    # Task 3: Market Assessment
    m_res = assess_market(listing)
    if m_res.geo_market_factor == 0 and m_res.market_env_factor == 0:
        print("  WARNING: Market Assessment returned neutral default. Likely failed/fallback.")
    results['market'] = benchmark_task("Market Assessment", assess_market, listing)
    
    return results

if __name__ == "__main__":
    all_res = run_all_benchmarks()
    print("\n--- Summary ---")
    for task, vals in all_res.items():
        print(f"{task}: {vals[0]:.4f}s, {vals[1]:.2f} TPS")
