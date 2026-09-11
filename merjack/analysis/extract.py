"""LLM-powered extraction of business listing data from raw text or URLs.
Used by the 'Magic Import' helper to pre-fill the Dynamic Entry form.
"""

from __future__ import annotations
import httpx
from typing import Optional
from ..llm import get_model
from ..models import Listing

_SYSTEM = (
    "You are a business data extraction expert. Your goal is to extract structured "
    "financials and descriptors from a business-for-sale listing. "
    "Be conservative: only extract values explicitly stated. "
    "Return a clean JSON object matching the Listing schema. "
    "Fields: title, asking_price, cash_flow_sde, revenue, ebitda, "
    "location, state, industry, year_established, employees, description."
)

def fetch_url_text(url: str) -> str:
    """Simple attempt to fetch raw text from a URL.
    Returns the text content or an empty string on failure.
    """
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            # Return basic text content (rudimentary)
            return resp.text
    except Exception:
        return ""

def extract_listing_from_text(text: str, model=None) -> Listing | None:
    """Convert raw listing text into a structured Listing object.
    If model is None, uses the configured 'explain' model for extraction.
    """
    if not text or len(text.strip()) < 10:
        return None
        
    if model is None:
        from ..llm import get_model
        model = get_model("explain")
        
    messages = [
        ("system", _SYSTEM),
        ("human", f"Extract the business details from the following text:\n\n{text}")
    ]
    
    try:
        # We use the model's structured output if available, otherwise plain JSON
        # For the sake of the extraction layer, we prefer a standard call and manual parse
        # or use the model's native structured output if the provider supports it.
        
        # Try structured output first
        try:
            structured_model = model.with_structured_output(Listing)
            return structured_model.invoke(messages)
        except Exception:
            # Fallback: Plain call + JSON parsing (via Pydantic validation)
            resp = model.invoke(messages)
            content = getattr(resp, "content", str(resp))
            
            # Clean potential markdown fences
            if isinstance(content, str):
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                
                import json
                return Listing.model_validate_json(content)
    except Exception:
        return None
