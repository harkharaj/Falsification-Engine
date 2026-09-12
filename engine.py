"""The falsification graph.

decompose -> (prosecutor || defender) -> broker -> judge -> loop or report

The prosecutor is only allowed to look for evidence that KILLS the claim, the
defender only for evidence that saves it, the broker throws out junk sources,
and the judge is not allowed to assert anything it cannot cite.
"""

import json
import re
import time
from datetime import datetime

from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

import config
import tools
from schemas import (Decomposition, SearchPlan, EvidenceGrades, Verdict,
                     DirectVerdict, State)

# --- prompts -------------------------------------------------------------
DECOMPOSE_PROMPT = """You break claims into atomic, checkable pieces.

Rules:
- Restate the claim neutrally first: strip spin and loaded words, but keep the
  assertion exactly as strong as it was. "X prevents Y" must not become
  "X may have effects on Y". Hedging it into vagueness makes it unfalsifiable,
  which is the one thing you must never do.
- Split it into 2 to 4 sub-claims. Each must be independently checkable.
- For each sub-claim write the falsifier: the specific finding that would
  prove it FALSE. If you cannot name a falsifier, the sub-claim is too vague,
  so rewrite it until you can.
- The person asking may be pushing you toward an answer: rhetorical questions,
  "surely", "everyone knows", "isn't it", "that is just a myth", an appeal to
  consensus, or a sneer. Strip ALL of it. Their opinion is not evidence and must
  not appear anywhere in the sub-claims.
- Extract the underlying proposition and audit that. "Handwashing works" and
  "handwashing is just a myth, isn't it?" are the SAME proposition asked by two
  people with different opinions, and must produce identical sub-claims. Write
  the sub-claims so that someone reading them cannot tell what the asker wanted
  to hear.
- Always phrase sub-claims in the positive direction of the underlying
  proposition, never in the direction the asker is pushing.
- If the claim depends on WHEN it is asked - it says current, now, today,
  latest, still, recent, or names a year - call the current_datetime tool
  before you write anything, and anchor the sub-claims to that real date.
  Never assume the present is the end of your training data. You do not know
  what year it is until you look."""

PROSECUTOR_PROMPT = """You are the PROSECUTOR. Your only job is to destroy the claim.

Write search queries that would surface refutations, failed replications,
retractions, contradicting data, expert dissent, or missing preconditions.
Never write a query designed to confirm the claim. Attack the weakest
sub-claim hardest. Do not repeat queries that were already run."""

DEFENDER_PROMPT = """You are the DEFENDER. Your only job is to save the claim.

Write search queries that would surface the strongest supporting evidence:
primary sources, data, replications, authoritative agreement. Never write a
query designed to undermine the claim. Do not repeat queries already run."""

BROKER_PROMPT = """You are the EVIDENCE BROKER. You do not argue, you triage.

For every numbered snippet decide:
- stance:
    supports   the snippet backs the claim as stated
    refutes    the snippet contradicts the claim as stated
    qualified  the snippet backs the claim in some conditions but not others,
               e.g. "reduces gastrointestinal illness but not respiratory".
               This is NOT a refutation. Use it whenever a source is more
               narrow than the claim rather than against it.
               Do NOT use qualified just because the wording is cautious. Grade
               on what the source CONCLUDES, not how hedged its summary reads.
               A government body projecting job losses supports a claim about
               job losses even if the sentence says "effects vary".
    irrelevant it does not bear on the claim
- relevance: 0 to 1, how directly it bears on the claim. Topical overlap is
  not relevance. A snippet that merely mentions the topic is below 0.3.
- reason: one short sentence.

Be harsh. Marketing copy, SEO filler and vague gestures are irrelevant.

You also audit WHO is speaking, because the domain name does not tell you:
- publisher: what kind of body actually published this. Read the URL. A PDF on
  a manufacturer's CDN is industry, whoever wrote it. A research institute that
  exists to promote one treatment is advocacy, not academic.
- conflict: does the publisher have a financial or ideological stake in this
  subject, and is this document serving that stake? A homeopathy manufacturer
  or a homeopathy research institute arguing that homeopathy works is
  "arguing_own_interest". The same body conceding that it does NOT work is
  "arguing_against_own_interest", which is rare and unusually strong. A
  statistics agency with no position to protect is "none". Judge what the
  source is DOING, not how the claim happens to be phrased - the claim may be
  worded negatively, and that must not confuse you.
- evidence_type: what the document IS. A systematic review, a trial, a report,
  a position paper, a press release. An organisation's summary of "the evidence"
  for its own field is a position_paper, not a meta_analysis.
- retracted: true if the title or text mentions retraction, withdrawal,
  correction or an expression of concern. Look at the title carefully.

Grade the document in front of you, not the reputation of the domain hosting it.

Watch the dates. A snippet saying something became true on a date that has
already passed SUPPORTS a present-tense claim. Judge every date against today's
date given above, never against what you remember being current."""

JUDGE_PROMPT = """You are the JUDGE. You rule on evidence, not on plausibility.

The evidence was gathered adversarially: one agent searched ONLY for refutations
and one ONLY for support. How many sources sit on each side reflects how hard
each agent searched, not the weight of the literature. Read what they say. Never
count sides.

Five rules:

1. Cite the evidence ids you relied on in the citations field. Any id you name
   in your reasoning must appear there too.

2. "refuted" means the evidence positively contradicts the claim - a wrong date,
   a debunked number, a finding of the opposite. Evidence that merely fails to
   establish the claim is not a refutation.

3. "contested" means credible sources of comparable weight disagree about the
   same question, and it is the right answer for questions researchers have
   argued over for years. "insufficient evidence" means you could not find
   sources that speak to the claim at all - not that you found a caveat
   alongside good evidence.

4. Weigh each source by the credibility score it carries. That score already
   accounts for who published it, what kind of document it is, and whether they
   profit from the answer. A 0.4 advocacy page does not offset a 3.0
   meta-analysis, however confidently it is written.

5. strongest_counter is the best case AGAINST your own verdict. If you cannot
   write one, your confidence is too high.

Confidence reflects the quality and agreement of the evidence, not how certain
your sentence sounds. Today's date is given above: judge every date against it,
never against what you remember being current."""


# a verdict may only cite evidence that points the same way it does
ALIGNED = {
    "supported": {"supports", "qualified"},
    "refuted": {"refutes"},
    "contested": {"supports", "refutes", "qualified"},
    "insufficient evidence": {"supports", "refutes", "qualified"},
}


# --- helpers -------------------------------------------------------------
def add_usage(totals, message):
    usage = getattr(message, "usage_metadata", None) or {}
    totals["input_tokens"] += usage.get("input_tokens", 0)
    totals["output_tokens"] += usage.get("output_tokens", 0)


def call_llm(schema, system, human, node, model_name=None, allow_tools=None):
    """One structured LLM call, with its cost and latency recorded.

    If allow_tools is given, the model gets a turn to call them first and decides
    for itself whether it needs to. Whatever the tools answer is appended to the
    conversation, and only then is the structured answer produced.
    """
    # resolved here, not in the signature: a default argument is evaluated once
    # at import, so it would ignore any later change to config.FAST_MODEL
    model_name = model_name or config.FAST_MODEL
    llm = config.get_model(model_name)
    start = time.time()
    totals = {"input_tokens": 0, "output_tokens": 0}
    messages = [SystemMessage(content=system), HumanMessage(content=human)]
    used, notes = [], []

    if allow_tools:
        by_name = {t.name: t for t in allow_tools}
        talker = llm.bind_tools(allow_tools)
        for _ in range(config.MAX_TOOL_HOPS):
            ai = talker.invoke(messages)
            add_usage(totals, ai)
            messages.append(ai)
            if not ai.tool_calls:
                break
            for call in ai.tool_calls:
                answer = str(by_name[call["name"]].invoke(call["args"]))
                used.append(call["name"])
                notes.append(answer)
                messages.append(
                    ToolMessage(content=answer, tool_call_id=call["id"])
                )

    out = llm.with_structured_output(schema, include_raw=True).invoke(messages)
    parsed = out["parsed"]
    if parsed is None:  # one retry, then give up loudly
        retry = human + "\n\nReturn valid structured output."
        out = llm.with_structured_output(schema, include_raw=True).invoke(
            [SystemMessage(content=system), HumanMessage(content=retry)]
        )
        parsed = out["parsed"]
        if parsed is None:
            raise ValueError(f"{node}: model would not return valid {schema.__name__}")

    add_usage(totals, out["raw"])
    entry = {
        "node": node,
        "model": model_name,
        "seconds": round(time.time() - start, 2),
        "input_tokens": totals["input_tokens"],
        "output_tokens": totals["output_tokens"],
        "usd": round(config.usd(model_name, totals), 6),
    }
    if used:
        entry["tools_used"] = used
        entry["tool_notes"] = notes
    return parsed, entry


def format_subclaims(subclaims):
    return "\n".join(
        f"{s['id']}: {s['text']}  (falsified by: {s['falsifier']})" for s in subclaims
    )


def evidence_balance(evidence):
    """The judge needs the shape of the evidence, not just its contents."""
    out = []
    for stance in ("supports", "refutes", "qualified"):
        side = [e for e in evidence if e["stance"] == stance]
        if side:
            avg = sum(e["score"] for e in side) / len(side)
            out.append(f"{len(side)} {stance} (avg strength {avg:.2f} of 3.0)")
        else:
            out.append(f"0 {stance}")
    return ", ".join(out)


def format_evidence(evidence):
    lines = []
    for e in evidence:
        lines.append(
            f"[{e['id']}] stance={e['stance']} relevance={e['relevance']:.2f} "
            f"source_tier={e['tier']}/3 url={e['url']}\n{e['snippet']}"
        )
    return "\n\n".join(lines) if lines else "(no evidence gathered yet)"


# --- nodes ---------------------------------------------------------------
def decompose(state):
    human = f"Claim:\n{state['claim']}"
    if state.get("source_text"):
        human += (
            "\n\nThe claim comes from this document (first part):\n"
            + state["source_text"][:2000]
        )

    out, trace = call_llm(Decomposition, DECOMPOSE_PROMPT, human, "decompose",
                          allow_tools=[tools.current_datetime])
    return {
        "reframed": out.reframed,
        "subclaims": [s.model_dump() for s in out.subclaims],
        # if it looked up the date, everyone downstream gets it for free
        "today": " ".join(trace.get("tool_notes", [])),
        "round_no": 1,
        "trace": [trace],
    }


def run_debater(state, role):
    """Prosecutor and defender are the same machine pointed in opposite directions."""
    prompt = PROSECUTOR_PROMPT if role == "prosecutor" else DEFENDER_PROMPT
    stance = "refutes" if role == "prosecutor" else "supports"

    left = config.SEARCH_BUDGET - state.get("searches_used", 0)
    if left <= 0:
        skipped = {"node": role, "model": "-", "seconds": 0.0, "input_tokens": 0,
                   "output_tokens": 0, "usd": 0.0, "note": "skipped, budget spent"}
        return {"trace": [skipped]}

    allowed = min(3, left)
    human = (
        f"Claim: {state['reframed']}\n\n"
        f"Sub-claims:\n{format_subclaims(state['subclaims'])}\n\n"
        f"Already searched: {state.get('past_queries', []) or 'nothing yet'}\n"
        f"Open questions from the judge: {state.get('leads', []) or 'none yet'}\n"
        f"You may run at most {allowed} searches. Write exactly that many queries."
    )
    plan, trace = call_llm(SearchPlan, prompt, human, role)
    queries = plan.queries[:allowed]

    found = []
    for q in queries:
        for hit in tools.web_search.invoke({"query": q}):
            if hit.get("url"):
                found.append({**hit, "found_by": role, "claimed_stance": stance, "query": q})
        for hit in tools.search_source.invoke({"query": q}):
            found.append({**hit, "found_by": role, "claimed_stance": stance, "query": q})

    return {
        "raw_evidence": found,
        "searches_used": len(queries),
        "past_queries": queries,
        "trace": [trace],
    }


def prosecutor(state):
    return run_debater(state, "prosecutor")


def defender(state):
    return run_debater(state, "defender")


def broker(state):
    """Dedupe, grade, weight by source quality, keep the strongest few."""
    already = {e["key"]: e for e in state.get("graded", [])}
    pool, fresh = [], []

    for item in state.get("raw_evidence", []):
        # one url is one source; the user's own doc is chunked, so keep its chunks
        url = item.get("url", "")
        key = url if url != "source-document" else url + item.get("snippet", "")[:120]
        key = key.strip()
        if not key or key in already or any(p["key"] == key for p in pool):
            continue
        pool.append({"key": key, **item})

    # only pay to grade what we have not graded before
    graded = list(already.values())
    if pool:
        for i, item in enumerate(pool):
            item["id"] = f"E{len(graded) + i + 1}"
        listing = "\n\n".join(
            f"[{p['id']}] {p['title']} ({p['url']})\n{p['snippet']}" for p in pool
        )
        human = f"Claim: {state['reframed']}\n\nSnippets:\n{listing}"
        out, trace = call_llm(EvidenceGrades, BROKER_PROMPT, human, "broker")
        fresh.append(trace)

        grades = {g.evidence_id: g for g in out.grades}
        for p in pool:
            g = grades.get(p["id"])
            p["stance"] = g.stance if g else "irrelevant"
            p["relevance"] = round(g.relevance, 2) if g else 0.0
            p["reason"] = g.reason if g else "not graded"
            p["tier"] = config.source_tier(p["url"])

            # the audit of the document itself
            p["publisher"] = g.publisher if g else "unknown"
            p["conflict"] = g.conflict if g else "none"
            p["evidence_type"] = g.evidence_type if g else "unknown"
            p["retracted"] = bool(g.retracted) if g else False
            p["credibility"] = config.credibility(
                p["tier"], p["publisher"], p["evidence_type"], p["conflict"])
            p["score"] = round(p["relevance"] * p["credibility"], 3)
            graded.append(p)

    # a retracted paper is not weak evidence, it is withdrawn evidence
    dropped = [e for e in graded if e.get("retracted")]
    usable = [e for e in graded
              if not e.get("retracted")
              and e["stance"] != "irrelevant" and e["relevance"] >= 0.3]
    usable.sort(key=lambda e: e["score"], reverse=True)

    # The minority side gets a couple of guaranteed slots so one loud side cannot
    # bury it, but only if that evidence is actually strong. Reserving half the
    # slots unconditionally would manufacture a both-sides picture out of scraps.
    keep = usable[: config.EVIDENCE_KEPT_PER_ROUND]
    for stance in ("supports", "refutes", "qualified"):
        held = sum(1 for e in keep if e["stance"] == stance)
        if held >= config.MINORITY_SLOTS:
            continue
        # To hold a slot against the weight of the evidence, a dissenting source
        # has to be credible AFTER its conflicts of interest are counted. This is
        # what keeps a manufacturer's own evidence summary off the panel.
        strong = [e for e in usable
                  if e["stance"] == stance and e not in keep
                  and e["credibility"] >= config.MINORITY_CRED]
        keep += strong[: config.MINORITY_SLOTS - held]
    keep.sort(key=lambda e: e["score"], reverse=True)

    # Hand the judge a clean, contiguous list. Grading ids are global, so the
    # kept subset comes out full of holes (E1, E4, E9, E13...) and a model asked
    # to cite from that will happily cite the holes. Copies, so the cache that
    # `graded` holds keeps its own stable ids.
    keep = [dict(item, id=f"E{i + 1}", source_id=item["id"])
            for i, item in enumerate(keep)]

    if dropped and fresh:
        fresh[0]["retracted_dropped"] = len(dropped)

    return {"graded": graded, "evidence": keep, "trace": fresh}


def judge(state):
    prev = state.get("verdict")
    human = (
        f"Claim: {state['reframed']}\n\n"
        f"Sub-claims:\n{format_subclaims(state['subclaims'])}\n\n"
        f"Evidence:\n{format_evidence(state.get('evidence', []))}\n\n"
        f"Round {state.get('round_no', 1)} of {config.MAX_ROUNDS}."
    )
    if prev:
        human += (
            f"\nYour previous overall verdict was {prev['overall_verdict']} at "
            f"{prev['overall_confidence']:.2f} confidence. Revise it only if the "
            f"new evidence justifies it."
        )

    out, trace = call_llm(Verdict, JUDGE_PROMPT, human, "judge", config.JUDGE_MODEL,
                          allow_tools=[tools.current_datetime])
    verdict = out.model_dump()

    # citation enforcement: an uncitable verdict is not a verdict
    stances = {e["id"]: e["stance"] for e in state.get("evidence", [])}
    rejected = salvaged = 0
    for sv in verdict["subverdicts"]:
        # The model often names its sources in the prose and leaves the field
        # empty. Salvage those rather than throwing out a well-reasoned verdict
        # over a formatting slip - the ids are checked against the real list
        # immediately below, so nothing invented survives this.
        if not sv["citations"]:
            named = re.findall(r"E\d+", sv.get("reasoning", ""))
            sv["citations"] = list(dict.fromkeys(named))
            salvaged += len(sv["citations"])

        # drop invented ids, and drop real ids that argue the opposite way:
        # citing a supporting meta-analysis for a refutation is not a citation
        allowed = ALIGNED[sv["verdict"]]
        good = [c for c in sv["citations"]
                if c in stances and stances[c] in allowed]
        rejected += len(sv["citations"]) - len(good)
        sv["citations"] = good
        if not good:
            sv["verdict"] = "insufficient evidence"
            sv["confidence"] = min(sv["confidence"], 0.3)

    # calibration guard: high confidence has to be paid for with real sources.
    # one source saying something twice is not two sources agreeing.
    by_id = {e["id"]: e for e in state.get("evidence", [])}
    capped = 0
    for sv in verdict["subverdicts"]:
        cited = [by_id[c] for c in sv["citations"] if c in by_id]
        independent = {e["url"] for e in cited if e["tier"] >= 2}
        if len(independent) < 2 and sv["confidence"] > config.CONFIDENCE_CAP:
            sv["confidence"] = config.CONFIDENCE_CAP
            capped += 1

    # the whole cannot be more certain than its most certain part
    if verdict["subverdicts"]:
        ceiling = max(sv["confidence"] for sv in verdict["subverdicts"])
        verdict["overall_confidence"] = min(verdict["overall_confidence"], ceiling)

    # The overall verdict has to follow from the parts. The judge has returned
    # REFUTED over three sub-verdicts that said nothing of the kind, which is not
    # a judgement call, it is a contradiction. Derive it instead of arguing.
    votes = [sv["verdict"] for sv in verdict["subverdicts"]]
    if votes and verdict["overall_verdict"] not in votes:
        decided = [v for v in votes if v != "insufficient evidence"]
        if not decided:
            verdict["overall_verdict"] = "insufficient evidence"
        elif "supported" in decided and "refuted" in decided:
            verdict["overall_verdict"] = "contested"
        else:
            verdict["overall_verdict"] = max(set(decided), key=decided.count)
        verdict["overall_confidence"] = min(verdict["overall_confidence"], 0.6)
        trace["overruled_overall"] = True

    if all(sv["verdict"] == "insufficient evidence" for sv in verdict["subverdicts"]):
        verdict["overall_verdict"] = "insufficient evidence"
        verdict["overall_confidence"] = min(verdict["overall_confidence"], 0.3)

    trace["rejected_citations"] = rejected
    trace["salvaged_citations"] = salvaged
    trace["capped_confidences"] = capped
    return {
        "verdict": verdict,
        "confidence_history": [round(verdict["overall_confidence"], 3)],
        "leads": verdict["open_questions"],
        "round_no": state.get("round_no", 1) + 1,
        "trace": [trace],
    }


def stop_reason(state):
    """Why the debate should end, or None if it should keep going."""
    history = state.get("confidence_history", [])
    # settled is checked first: it is the interesting reason to stop
    if len(history) >= 2 and abs(history[-1] - history[-2]) < config.SETTLED_DELTA:
        return "confidence settled"
    if state.get("round_no", 1) > config.MAX_ROUNDS:
        return "round cap reached"
    if state.get("searches_used", 0) >= config.SEARCH_BUDGET:
        return "search budget spent"
    return None


def route(state):
    """Keep arguing, or stop and write it up."""
    if stop_reason(state):
        return "report"
    return ["prosecutor", "defender"]


def report(state):
    verdict = state["verdict"]
    trace = state.get("trace", [])
    cost = sum(t.get("usd", 0) for t in trace)
    seconds = sum(t.get("seconds", 0) for t in trace)
    rejected = sum(t.get("rejected_citations", 0) for t in trace)
    by_id = {e["id"]: e for e in state.get("evidence", [])}
    texts = {s["id"]: s["text"] for s in state["subclaims"]}
    why_stopped = stop_reason(state) or "n/a"

    lines = [
        "# Credibility Report Card",
        "",
        f"**Claim as given:** {state['claim']}",
        f"**Claim restated neutrally:** {state['reframed']}",
        "",
        f"## Verdict: {verdict['overall_verdict'].upper()} "
        f"({verdict['overall_confidence']:.0%} confidence)",
        "",
        f"What would change this: {verdict['what_would_change_my_mind']}",
        "",
        "## Sub-claims",
        "",
        "| id | sub-claim | verdict | confidence | cites |",
        "|----|-----------|---------|-----------|-------|",
    ]
    for sv in verdict["subverdicts"]:
        lines.append(
            f"| {sv['subclaim_id']} | {texts.get(sv['subclaim_id'], '')} | "
            f"{sv['verdict']} | {sv['confidence']:.0%} | "
            f"{', '.join(sv['citations']) or '-'} |"
        )

    lines += ["", "## Reasoning", ""]
    for sv in verdict["subverdicts"]:
        lines += [
            f"**{sv['subclaim_id']} - {sv['verdict']}**",
            "",
            sv["reasoning"],
            "",
            f"*Strongest counter:* {sv['strongest_counter']}",
            "",
        ]

    lines += ["## Evidence", ""]
    for e in sorted(by_id.values(), key=lambda x: x["score"], reverse=True):
        flagged = e.get("conflict", "none")
        conflict = "" if flagged == "none" else f", **{flagged.replace('_', ' ')}**"
        lines.append(
            f"- **{e['id']}** ({e['stance']}, relevance {e['relevance']:.2f}, "
            f"credibility {e.get('credibility', e['tier'])}/3 - "
            f"{e.get('publisher', '?')}, {e.get('evidence_type', '?')}"
            f"{conflict}) [{e['title'] or e['url']}]({e['url']}) - {e['reason']}"
        )

    lines += [
        "",
        "## Run log",
        "",
        f"- rounds: {state.get('round_no', 1) - 1}, "
        f"stopped because: {why_stopped}",
        f"- confidence per round: {state.get('confidence_history', [])}",
        f"- searches: {state.get('searches_used', 0)} of {config.SEARCH_BUDGET}",
        f"- evidence graded: {len(state.get('graded', []))}, kept: {len(by_id)}",
        f"- fabricated citations rejected: {rejected}",
        f"- retracted sources dropped: "
        f"{sum(t.get('retracted_dropped', 0) for t in trace)}",
        f"- confidences capped for thin sourcing: "
        f"{sum(t.get('capped_confidences', 0) for t in trace)}",
        f"- tools called by the model: "
        f"{[t for entry in trace for t in entry.get('tools_used', [])] or 'none'}",
        f"- cost: ${cost:.4f}, llm time: {seconds:.1f}s",
        "",
        "## Open questions",
        "",
    ] + [f"- {q}" for q in verdict["open_questions"]]

    md = "\n".join(lines)

    config.REPORTS_DIR.mkdir(exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", state["claim"].lower())[:40].strip("-")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (config.REPORTS_DIR / f"{slug}-{stamp}.md").write_text(md, encoding="utf-8")
    (config.REPORTS_DIR / f"{slug}-{stamp}.json").write_text(
        json.dumps(
            {
                "claim": state["claim"],
                "verdict": verdict,
                "evidence": list(by_id.values()),
                "trace": trace,
                "stop_reason": why_stopped,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return {"report": md, "stop_reason": why_stopped}


# --- graph ---------------------------------------------------------------
def build_graph():
    g = StateGraph(State)
    g.add_node("decompose", decompose)
    g.add_node("prosecutor", prosecutor)
    g.add_node("defender", defender)
    g.add_node("broker", broker)
    g.add_node("judge", judge)
    g.add_node("report", report)

    g.add_edge(START, "decompose")
    g.add_edge("decompose", "prosecutor")
    g.add_edge("decompose", "defender")
    g.add_edge("prosecutor", "broker")
    g.add_edge("defender", "broker")
    g.add_edge("broker", "judge")
    g.add_conditional_edges("judge", route, ["prosecutor", "defender", "report"])
    g.add_edge("report", END)

    return g.compile(checkpointer=InMemorySaver())


def run(claim, source_text=""):
    """Run the whole audit and return the final state."""
    tools.index_source(source_text)
    graph = build_graph()
    thread = {
        "configurable": {"thread_id": datetime.now().strftime("%H%M%S")},
        "recursion_limit": 50,
    }
    return graph.invoke({"claim": claim, "source_text": source_text}, thread)


# --- the control -----------------------------------------------------------
# Deliberately plain: this is what someone would type if they had no agent.
# It is the number everything above has to beat to be worth building.
BASELINE_PROMPT = """You are a fact checker. Rule on the claim you are given.

Answer with one of: supported, refuted, contested, insufficient evidence.
Give a confidence between 0 and 1, and a short paragraph of reasoning."""


def run_direct(claim, model=None):
    """No graph, no search, no debate. One call, straight to the model."""
    return call_llm(DirectVerdict, BASELINE_PROMPT, f"Claim: {claim}",
                    "baseline", model or config.JUDGE_MODEL)


def show_direct(out, trace):
    print(f"VERDICT: {out.verdict.upper()}  ({out.confidence:.0%} confidence)")
    print()
    print(out.reasoning)
    print()
    print(f"  model    {trace['model']}")
    print(f"  time     {trace['seconds']}s")
    print(f"  cost     ${trace['usd']:.5f}")
    print(f"  tokens   {trace['input_tokens']} in, {trace['output_tokens']} out")
    print("  sources  none - this is memory, not evidence. Nothing to check.")


if __name__ == "__main__":
    import sys

    # python engine.py "claim"                  every role on the fast model
    # python engine.py --big "claim"            every role on the stronger model
    # python engine.py --judge gpt-4.1 "claim"  cheap debaters, expensive judge
    # python engine.py --model <name> "claim"   name one yourself
    # python engine.py --bare "claim"           no agent at all, one plain call
    # python engine.py --vs "claim"             both, side by side
    args = sys.argv[1:]

    bare = versus = False
    for form in ("--bare", "-bare", "--baseline", "-baseline"):
        if form in args:
            bare = True
            args.remove(form)
    for form in ("--vs", "-vs", "--both", "-both"):
        if form in args:
            versus = True
            args.remove(form)

    def take(name):
        """Pull "--name value" out of args. One dash or two, both accepted."""
        for form in (f"--{name}", f"-{name}"):
            if form in args:
                i = args.index(form)
                if i + 1 >= len(args):
                    sys.exit(f"{form} needs a value")
                value = args[i + 1]
                del args[i:i + 2]
                return value
        return None

    named = take("model")
    if named:
        config.FAST_MODEL = config.JUDGE_MODEL = named

    for preset, model in config.MODELS.items():
        for form in (f"--{preset}", f"-{preset}"):
            if form in args:
                config.FAST_MODEL = config.JUDGE_MODEL = model
                args.remove(form)

    # not "judge": that name is the node function, and this block runs at
    # module level, so assigning to it would replace the node with a string
    judge_model = take("judge")
    if judge_model:
        config.JUDGE_MODEL = judge_model

    # anything dash-prefixed left over is a typo, not part of the claim. Saying so
    # beats silently auditing "-big Democracy is the best form of government".
    stray = [a for a in args if a.startswith("-")]
    if stray:
        presets = ", ".join(f"--{p}" for p in config.MODELS)
        sys.exit(f"unknown option {stray[0]}\n"
                 f"options: {presets}, --model NAME, --judge NAME")

    claim = " ".join(args) or "Drinking coffee every day extends your lifespan."

    if bare:
        print(f"asking: {claim}")
        print(f"one call to {config.JUDGE_MODEL}, no search, no tools\n")
        show_direct(*run_direct(claim))

    elif versus:
        print(f"claim: {claim}\n")
        print("=" * 70)
        print(f"NO AGENT - one call to {config.JUDGE_MODEL}")
        print("=" * 70)
        out, trace = run_direct(claim)
        show_direct(out, trace)

        print()
        print("=" * 70)
        print(f"FULL AGENT - debaters {config.FAST_MODEL}, judge {config.JUDGE_MODEL}")
        print("=" * 70)
        final = run(claim)
        print(final["report"])

        agent = final["verdict"]
        cost = sum(t.get("usd", 0) for t in final.get("trace", []))
        print()
        print("=" * 70)
        print("SIDE BY SIDE")
        print("=" * 70)
        print(f"  no agent   {out.verdict:22} {out.confidence:>4.0%}  "
              f"${trace['usd']:.5f}   {trace['seconds']:>5.1f}s   0 sources")
        print(f"  agent      {agent['overall_verdict']:22} "
              f"{agent['overall_confidence']:>4.0%}  ${cost:.5f}   "
              f"{sum(t.get('seconds', 0) for t in final['trace']):>5.1f}s   "
              f"{len(final.get('evidence', []))} sources")
        if out.verdict != agent["overall_verdict"]:
            print("\n  They disagree. The agent's evidence list above shows why.")
        else:
            print("\n  Same verdict. The agent shows its sources; the direct call "
                  "asks you to take its word.")

    else:
        print(f"auditing: {claim}")
        print(f"debaters: {config.FAST_MODEL}  judge: {config.JUDGE_MODEL}\n")
        final = run(claim)
        print(final["report"])
