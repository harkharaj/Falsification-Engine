"""Every structured output the graph produces, plus the graph state itself."""

import operator
from typing import Annotated, Literal, TypedDict
from pydantic import BaseModel, Field

VERDICTS = ["supported", "refuted", "contested", "insufficient evidence"]


# --- what the decomposer returns ----------------------------------------
class SubClaim(BaseModel):
    id: str = Field(description="short id like S1, S2")
    text: str = Field(description="one atomic, checkable statement")
    falsifier: str = Field(description="what evidence would prove this false")


class Decomposition(BaseModel):
    subclaims: list[SubClaim]
    reframed: str
    today: str = Field(description="the claim restated neutrally, no loaded words")


# --- what each debater returns ------------------------------------------
class SearchPlan(BaseModel):
    queries: list[str] = Field(description="web search queries, 3 to 5 words each")


# --- what the evidence broker returns -----------------------------------
class EvidenceGrade(BaseModel):
    evidence_id: str
    stance: Literal["supports", "refutes", "qualified", "irrelevant"]
    relevance: float = Field(ge=0, le=1)
    reason: str = Field(description="one short sentence")

    # who published it, and do they have a dog in this fight
    publisher: Literal[
        "government", "academic", "journal", "news", "encyclopedia",
        "advocacy", "industry", "personal", "unknown",
    ] = Field(description="what kind of organisation published this")
    conflict: Literal["none", "arguing_own_interest",
                      "arguing_against_own_interest"] = Field(
        description="Does the publisher have a financial or ideological stake in "
                    "this subject, and if so, is this document arguing FOR that "
                    "stake or AGAINST it? Answer in one step: do not reason about "
                    "whether the claim is phrased positively or negatively, just "
                    "say whether this source is serving its own interest here.")
    evidence_type: Literal[
        "meta_analysis", "trial", "observational", "report",
        "position_paper", "press_release", "news_article", "unknown",
    ] = Field(description="what kind of evidence this actually is")
    retracted: bool = Field(
        description="true if the title or text mentions retraction, withdrawal, "
                    "correction or an expression of concern")


class EvidenceGrades(BaseModel):
    grades: list[EvidenceGrade]


# --- what the judge returns ---------------------------------------------
class SubVerdict(BaseModel):
    subclaim_id: str
    verdict: Literal["supported", "refuted", "contested", "insufficient evidence"]
    confidence: float = Field(ge=0, le=1)
    reasoning: str
    citations: list[str] = Field(description="evidence ids like E3 that back this")
    strongest_counter: str = Field(description="the best argument against this verdict")


class Verdict(BaseModel):
    subverdicts: list[SubVerdict]
    overall_verdict: Literal["supported", "refuted", "contested", "insufficient evidence"]
    overall_confidence: float = Field(ge=0, le=1)
    what_would_change_my_mind: str
    open_questions: list[str] = Field(description="gaps worth another search round")


# --- the no-agent baseline: one call, no search, no evidence ---
class DirectVerdict(BaseModel):
    verdict: Literal["supported", "refuted", "contested", "insufficient evidence"]
    confidence: float = Field(ge=0, le=1)
    reasoning: str


# --- graph state ---------------------------------------------------------
# raw_evidence is written by two branches at once, so it needs a reducer.
class State(TypedDict, total=False):
    claim: str
    source_text: str
    reframed: str
    today: str
    subclaims: list[dict]
    round_no: int
    raw_evidence: Annotated[list[dict], operator.add]
    graded: list[dict]
    evidence: list[dict]
    past_queries: Annotated[list[str], operator.add]
    verdict: dict
    confidence_history: Annotated[list[float], operator.add]
    leads: list[str]
    searches_used: Annotated[int, operator.add]
    trace: Annotated[list[dict], operator.add]
    stop_reason: str
    report: str
