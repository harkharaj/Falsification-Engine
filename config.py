"""All the knobs in one place: models, budgets, pricing, stop rules."""

import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

load_dotenv()

ROOT = Path(__file__).parent
REPORTS_DIR = ROOT / "reports"
EVALS_DIR = ROOT / "evals"

# --- models -------------------------------------------------------------
FAST_MODEL = "gpt-4o-mini"      # decompose, search queries, evidence grading
JUDGE_MODEL = "gpt-4o-mini"     # the decisive call, worth paying more for

# presets for the --fast / --big flags. On the hard eval set big scored 75%
# against fast's 50%, for roughly 3x the cost per audit.
MODELS = {
    "fast": "gpt-4o-mini",
    "big": "gpt-4.1-mini",
    "huge": "gpt-4.1",
}

# --- falsification budget -----------------------------------------------
MAX_TOOL_HOPS = 2               # how many times a node may reach for a tool
MAX_ROUNDS = 3                  # hard cap on debate rounds
SEARCH_BUDGET = 18              # total web searches allowed per run
RESULTS_PER_SEARCH = 4
EVIDENCE_KEPT_PER_ROUND = 8     # broker keeps only the strongest N
MINORITY_BAR = 0.7              # relevance a low-tier dissenting source must clear
MINORITY_SLOTS = 3              # slots each stance is topped up to, if it earns them
SETTLED_DELTA = 0.05            # stop early if confidence moves less than this
CONFIDENCE_CAP = 0.7            # ceiling unless 2+ independent credible sources agree

# --- pricing, USD per 1M tokens -----------------------------------------
PRICING = {
    "gpt-4o-mini": {"in": 0.15, "out": 0.60},
    "gpt-4.1-mini": {"in": 0.40, "out": 1.60},
    "gpt-4.1": {"in": 2.00, "out": 8.00},
    "gpt-4o": {"in": 2.50, "out": 10.00},
}

# source tiers -> prior credibility, used by the evidence broker
DOMAIN_TIERS = {
    3: [".gov", ".edu", "who.int", "nature.com", "science.org", "arxiv.org",
        "nih.gov", "nasa.gov", "ieee.org", "pubmed"],
    2: ["wikipedia.org", "reuters.com", "apnews.com", "bbc.", "nytimes.com",
        "economist.com", "ft.com", "britannica.com"],
}


# Whose key the audit currently running is spending. The Streamlit app sets this
# for the duration of one run and clears it afterwards, holding a process-wide
# lock while it does, so a visitor who pasted their own key can never have it
# picked up by somebody else's run. None means "fall back to OPENAI_API_KEY in
# the environment", which is what the CLI and the eval harness do.
ACTIVE_API_KEY = None


def _key():
    return ACTIVE_API_KEY or os.environ.get("OPENAI_API_KEY")


def get_model(name=FAST_MODEL, temperature=0):
    return ChatOpenAI(model=name, temperature=temperature, api_key=_key())


def get_embeddings():
    return OpenAIEmbeddings(model="text-embedding-3-small", api_key=_key())


# A domain list can only ever describe the DOMAIN. It cannot tell you that this
# particular nature.com article was retracted, or that this PDF is hosted on a
# homeopathy manufacturer's CDN. So the tier is a ceiling, and the broker's audit
# of the actual document pushes it down from there.
PUBLISHER_CEILING = {
    "government": 3, "academic": 3, "journal": 3,
    "encyclopedia": 2, "news": 2,
    "advocacy": 1, "industry": 1, "personal": 1, "unknown": 1,
}

EVIDENCE_WEIGHT = {
    "meta_analysis": 1.2, "trial": 1.1, "observational": 1.0,
    "report": 0.9, "news_article": 0.8, "unknown": 0.8,
    "position_paper": 0.5, "press_release": 0.4,
}

CONFLICT_PENALTY = 0.3          # arguing its own interest
AGAINST_INTEREST_BONUS = 1.3    # arguing against its own interest, which is telling
MINORITY_CRED = 1.5             # credibility a dissenting source needs for a kept slot


def credibility(tier, publisher, evidence_type, conflict):
    """0 to 3. What this document is worth, not what its domain is worth.

    What the publisher IS leads, because no domain list can be complete - it had
    thelancet.com at tier 1 and capped a definitive meta-analysis below an
    advocacy page. The domain list is now only a fallback for sources the broker
    could not identify.
    """
    if publisher == "unknown":
        score = float(tier)
    else:
        score = float(PUBLISHER_CEILING.get(publisher, 1))
        if tier >= 2:                 # the domain list agrees it is reputable
            score = max(score, float(tier))

    score *= EVIDENCE_WEIGHT.get(evidence_type, 0.8)

    # A conflict of interest cuts both ways. A homeopathy manufacturer saying
    # homeopathy works is worth almost nothing. The same manufacturer saying it
    # does NOT work is worth a great deal, because nobody argues against
    # themselves without reason.
    if conflict == "arguing_own_interest":
        score *= CONFLICT_PENALTY
    elif conflict == "arguing_against_own_interest":
        score *= AGAINST_INTEREST_BONUS

    return round(min(score, 3.0), 2)


def source_tier(url):
    """Cheap prior on how much a domain should be trusted (1 = unknown blog)."""
    url = (url or "").lower()
    for tier, markers in DOMAIN_TIERS.items():
        if any(m in url for m in markers):
            return tier
    return 1


def usd(model, usage):
    """usage is the usage_metadata dict hanging off an AIMessage."""
    if not usage:
        return 0.0
    price = PRICING.get(model, PRICING[FAST_MODEL])
    return (usage.get("input_tokens", 0) * price["in"] / 1_000_000
            + usage.get("output_tokens", 0) * price["out"] / 1_000_000)
