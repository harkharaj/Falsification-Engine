"""Streamlit front end. Watch the prosecutor and defender fight, live.

run with:  streamlit run app.py
"""

import os
import sys
import threading

# Streamlit Cloud ships an old system sqlite3 on some images, and chromadb (via
# langchain_chroma, imported by tools) refuses to load against anything below
# 3.35. pysqlite3-binary is a modern sqlite3 built as a wheel; swap it in before
# anything imports chromadb. Locally this is a no-op - the wheel is linux-only
# and the system sqlite3 is already new enough.
try:                                    # pragma: no cover - deployment shim
    import sqlite3
    if sqlite3.sqlite_version_info < (3, 35, 0):
        __import__("pysqlite3")
        sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    pass

from datetime import datetime

import streamlit as st
from pypdf import PdfReader

import config
import engine
import tools

st.set_page_config(page_title="Falsification Engine", page_icon="X", layout="wide")


def secret(name, fallback=None):
    """Streamlit secrets when deployed, nothing when running locally."""
    try:
        return st.secrets.get(name, fallback)
    except Exception:          # no secrets.toml at all, which is fine locally
        return fallback


@st.cache_resource
def run_lock():
    """One audit at a time, process wide.

    config.ACTIVE_API_KEY is a module global, so two audits overlapping inside
    the same Streamlit process could otherwise read each other's key. Serialising
    runs keeps that global honest, and on a demo it is a reasonable cost control
    besides.
    """
    return threading.Lock()


def apply_demo_caps():
    """Cap what one visitor can spend on the author's key."""
    config.MAX_ROUNDS = 2
    config.SEARCH_BUDGET = 8
    config.FAST_MODEL = config.JUDGE_MODEL = "gpt-4o-mini"


def render_gate(owner_key, password):
    """Two ways in: bring your own key, or borrow the author's with a password."""
    st.title("Falsification Engine")
    st.caption(
        "An audit costs real OpenAI credit, so pick which key pays for it."
    )

    own, borrow = st.tabs(["Use your own API key", "Use the demo password"])

    with own:
        entered = st.text_input(
            "OpenAI API key", type="password", key="byok_input",
            placeholder="sk-...",
        )
        st.caption(
            "Held in this browser session only. It is never written to disk, "
            "never logged, and never put in a process-wide variable another "
            "visitor could read. Close the tab and it is gone."
        )
        if st.button("Start with my key", type="primary"):
            if not entered.strip():
                st.error("Paste a key first.")
            elif not entered.strip().startswith("sk-"):
                st.error("That does not look like an OpenAI key.")
            else:
                st.session_state["api_key"] = entered.strip()
                st.session_state["key_source"] = "visitor"
                st.rerun()

    with borrow:
        if not (owner_key and password):
            st.info("The shared demo key is not configured on this deployment.")
        else:
            guess = st.text_input("Password", type="password", key="pw_input")
            st.caption(
                "Runs on the author's key, so it is capped: 2 debate rounds, "
                "8 searches, `gpt-4o-mini`. Do not have the password? Use your "
                "own key on the other tab."
            )
            if st.button("Unlock the demo"):
                if guess == password:
                    st.session_state["api_key"] = owner_key
                    st.session_state["key_source"] = "owner"
                    st.rerun()
                else:
                    st.error("Not that one.")

    st.stop()


def setup_access():
    """Work out whose key this session spends, and how much it may spend.

    Locally none of this renders: load_dotenv() in config.py finds the .env,
    no password is configured, and the app behaves exactly as it always did.
    """
    owner_key = secret("OPENAI_API_KEY")
    password = secret("APP_PASSWORD")

    if not st.session_state.get("api_key"):
        env_key = os.environ.get("OPENAI_API_KEY")
        if env_key and not password:
            # Running locally off a .env. Nothing to gate.
            st.session_state["api_key"] = env_key
            st.session_state["key_source"] = "local"
        else:
            render_gate(owner_key, password)

    if secret("DEMO_MODE") and st.session_state.get("key_source") == "owner":
        apply_demo_caps()
        return True
    return False


DEMO = setup_access()

VERDICT_COLOR = {
    "supported": "green",
    "refuted": "red",
    "contested": "orange",
    "insufficient evidence": "grey",
}

NODE_LABEL = {
    "decompose": "Breaking the claim into falsifiable pieces",
    "prosecutor": "Prosecutor hunting for refutations",
    "defender": "Defender hunting for support",
    "broker": "Broker grading sources",
    "judge": "Judge ruling on the evidence",
    "report": "Writing the report card",
}

st.title("Falsification Engine")
st.caption(
    "Most tools try to answer your question. This one tries to destroy your claim, "
    "and only believes what survives."
)

# --- inputs --------------------------------------------------------------
with st.sidebar:
    source = st.session_state.get("key_source")
    if source == "visitor":
        st.success("Running on your own API key.")
        if st.button("Forget my key and sign out"):
            st.session_state.clear()
            st.rerun()
    elif source == "owner":
        st.info(
            f"Shared demo key: {config.MAX_ROUNDS} rounds, "
            f"{config.SEARCH_BUDGET} searches, `{config.FAST_MODEL}`. "
            "Paste your own key instead to lift the caps."
        )
        if st.button("Sign out"):
            st.session_state.clear()
            st.rerun()

with st.sidebar:
    st.header("Models")
    # only models we have pricing for, so the cost tracker stays honest
    choices = list(config.PRICING)
    if DEMO:
        choices = ["gpt-4o-mini"]
    config.FAST_MODEL = st.selectbox(
        "Decompose, debaters, broker", choices,
        index=choices.index(config.FAST_MODEL),
        help="Writes the sub-claims and search queries, grades the evidence. "
             "Called most often, so this drives the cost.",
    )
    config.JUDGE_MODEL = st.selectbox(
        "Judge", choices,
        index=choices.index(config.JUDGE_MODEL),
        help="Makes the actual ruling. Most reasoning failures happen here, so "
             "a stronger model earns its keep on this one more than the others.",
    )
    fast_price = config.PRICING[config.FAST_MODEL]
    judge_price = config.PRICING[config.JUDGE_MODEL]
    st.caption(
        f"per 1M tokens - workers ${fast_price['in']}/${fast_price['out']}, "
        f"judge ${judge_price['in']}/${judge_price['out']}"
    )

    if not DEMO:
        st.header("Budget")
        config.MAX_ROUNDS = st.slider("Debate rounds", 1, 5, config.MAX_ROUNDS)
        config.SEARCH_BUDGET = st.slider("Search budget", 4, 30, config.SEARCH_BUDGET)
        config.SETTLED_DELTA = st.slider(
            "Stop when confidence moves less than", 0.0, 0.3,
            config.SETTLED_DELTA, 0.01,
        )

    st.header("Optional source")
    st.caption("Ground the audit in a document the claim came from.")
    uploaded = st.file_uploader("PDF", type="pdf")
    url = st.text_input("or a page url")
    pasted = st.text_area("or paste text", height=120)

claim = st.text_input(
    "Claim to audit",
    placeholder="e.g. Remote work reduces engineering productivity",
)
go = st.button("Audit this claim", type="primary", disabled=not claim.strip())


def load_source():
    if uploaded:
        return " ".join((p.extract_text() or "") for p in PdfReader(uploaded).pages)
    if url.strip():
        return tools.fetch_page.invoke({"url": url.strip()})
    return pasted.strip()


def run_audit(claim, source_text):
    """One audit, start to finish, streaming each node as it lands."""
    if source_text:
        chunks = tools.index_source(source_text)
        st.info(f"Indexed your source into {chunks} chunks, the debaters can quote it.")
    else:
        tools.index_source("")

    graph = engine.build_graph()
    thread = {
        "configurable": {"thread_id": datetime.now().strftime("%H%M%S%f")},
        "recursion_limit": 50,
    }

    state = {}
    round_no = 1
    with st.status("Running the debate...", expanded=True) as status:
        for chunk in graph.stream(
            {"claim": claim, "source_text": source_text}, thread, stream_mode="updates"
        ):
            for node, update in chunk.items():
                st.write(f"**{NODE_LABEL.get(node, node)}**")

                if node == "decompose":
                    for s in update["subclaims"]:
                        st.write(f"- `{s['id']}` {s['text']}")
                elif node in ("prosecutor", "defender"):
                    for q in update.get("past_queries", []):
                        st.write(f"  - searched: *{q}*")
                elif node == "broker":
                    st.write(f"  - {len(update['evidence'])} pieces of evidence kept")
                elif node == "judge":
                    v = update["verdict"]
                    st.write(
                        f"  - round {round_no}: **{v['overall_verdict']}** "
                        f"at {v['overall_confidence']:.0%}"
                    )
                    round_no += 1

                # stream_mode="updates" gives deltas, so build the state ourselves
                for key, value in update.items():
                    if key in ("trace", "raw_evidence", "confidence_history", "past_queries"):
                        state[key] = state.get(key, []) + value
                    else:
                        state[key] = value

        status.update(label="Debate finished", state="complete")

    st.session_state["state"] = state


# --- run -----------------------------------------------------------------
if go:
    source_text = load_source()

    # Everything that can reach OpenAI happens inside the lock, with this
    # session's key installed, and the key comes back out again afterwards.
    with run_lock():
        config.ACTIVE_API_KEY = st.session_state["api_key"]
        try:
            run_audit(claim, source_text)
        finally:
            config.ACTIVE_API_KEY = None

# --- results -------------------------------------------------------------
VERDICT_MEANING = {
    "supported": "The evidence positively backs the claim as stated.",
    "refuted": "The evidence positively contradicts the claim. Not the same as "
               "unproven - something found had to say the opposite.",
    "contested": "Credible sources of comparable weight disagree. A real "
                 "controversy, not a way of avoiding the question.",
    "insufficient evidence": "Nothing found actually settles it. The engine is "
                             "refusing to guess, which is a result, not a failure.",
}

STANCE_MEANING = {
    "supports": "backs the claim",
    "refutes": "contradicts the claim",
    "qualified": "backs it only in narrower conditions - a narrowing, not a refutation",
}

TIER_MEANING = {
    3: "tier 3 - peer reviewed, government, major journal",
    2: "tier 2 - encyclopaedia or established news",
    1: "tier 1 - blog, advocacy site or unknown source",
}

PUBLISHER_MEANING = {
    "government": "a government body or public health agency",
    "academic": "a university, research body or academic press",
    "journal": "a peer reviewed journal",
    "news": "a news organisation",
    "encyclopedia": "an encyclopaedia or reference work",
    "advocacy": "an organisation that exists to promote a position",
    "industry": "a company or trade body with commercial interests here",
    "personal": "a personal blog or individual",
    "unknown": "could not be identified",
}

TYPE_MEANING = {
    "meta_analysis": "a systematic review or meta-analysis, the strongest form",
    "trial": "a controlled trial",
    "observational": "an observational study",
    "report": "a report or summary",
    "position_paper": "a position paper - an argument, not a study",
    "press_release": "a press release - marketing, not evidence",
    "news_article": "a news article reporting on something else",
    "unknown": "unclear what kind of document this is",
}

CONFLICT_MEANING = {
    "arguing_own_interest":
        "This publisher profits or benefits from the answer it is giving, so its "
        "score is cut to 30%.",
    "arguing_against_own_interest":
        "This publisher argues AGAINST its own interest here. Nobody does that "
        "without reason, so its score is raised by 30%.",
}


def explain_score(e):
    """Walk through exactly how this source's weight was arrived at."""
    publisher = e.get("publisher", "unknown")
    kind = e.get("evidence_type", "unknown")
    conflict = e.get("conflict", "none")
    ceiling = config.PUBLISHER_CEILING.get(publisher, 1)
    weight = config.EVIDENCE_WEIGHT.get(kind, 0.8)

    steps = [
        f"**Publisher: {publisher}** - {PUBLISHER_MEANING.get(publisher, '')}. "
        f"Starts at **{ceiling} of 3**.",
        f"**Document type: {kind.replace('_', ' ')}** - {TYPE_MEANING.get(kind, '')}. "
        f"Multiplies by **{weight}**.",
    ]
    if conflict == "none":
        steps.append("**Conflict of interest: none found.** No adjustment.")
    else:
        factor = (config.CONFLICT_PENALTY if conflict == "arguing_own_interest"
                  else config.AGAINST_INTEREST_BONUS)
        steps.append(f"**Conflict: {conflict.replace('_', ' ')}.** "
                     f"{CONFLICT_MEANING.get(conflict, '')} Multiplies by **{factor}**.")
    steps.append(
        f"Credibility **{e.get('credibility', e['tier'])} of 3**, times relevance "
        f"**{e['relevance']:.2f}**, gives this source a weight of "
        f"**{e['score']:.2f}**."
    )
    if e.get("tier", 1) >= 2:
        steps.append(f":grey[The domain is also on the known-reputable list "
                     f"(tier {e['tier']}), which backs up the publisher reading.]")
    return steps

state = st.session_state.get("state")
if state and state.get("verdict"):
    verdict = state["verdict"]
    overall = verdict["overall_verdict"]
    color = VERDICT_COLOR.get(overall, "grey")
    subclaims = {s["id"]: s for s in state["subclaims"]}
    evidence = state.get("evidence", [])
    by_id = {e["id"]: e for e in evidence}
    trace = state.get("trace", [])

    st.divider()
    st.markdown(f"## :{color}[{overall.upper()}]")
    st.progress(verdict["overall_confidence"],
                text=f"{verdict['overall_confidence']:.0%} confidence")
    st.caption(VERDICT_MEANING.get(overall, ""))

    st.markdown(f"**Your claim, restated neutrally:** {state['reframed']}")
    st.caption(
        "Written before any searching, with the spin stripped out. If this does "
        "not match what you meant, everything below is answering the wrong question."
    )
    st.info(f"**What would change this verdict:** "
            f"{verdict['what_would_change_my_mind']}")

    history = state.get("confidence_history", [])
    if len(history) > 1:
        st.markdown("#### Confidence after each round")
        st.caption(
            "One round = both agents search, the broker grades what they found, "
            "the judge rules. The debate stops when this number stops moving."
        )
        cols = st.columns(len(history))
        for i, (col, conf) in enumerate(zip(cols, history)):
            delta = None if i == 0 else f"{(conf - history[i - 1]):+.0%}"
            col.metric(f"Round {i + 1}", f"{conf:.0%}", delta)

    # --- sub-claims ------------------------------------------------------
    st.subheader("Sub-claims")
    st.markdown(
        "Your claim was split into **atomic pieces** that can each be checked "
        "separately - `S1`, `S2` and so on. A claim can easily be true in one "
        "part and false in another, which a single yes or no would hide. Each "
        "piece also carries a **falsifier**: the specific finding that would "
        "prove it false. If no falsifier can be written, the claim is too vague "
        "to check."
    )
    st.dataframe(
        [
            {
                "id": sv["subclaim_id"],
                "sub-claim": subclaims.get(sv["subclaim_id"], {}).get("text", ""),
                "verdict": sv["verdict"],
                "confidence": f"{sv['confidence']:.0%}",
                "backed by": ", ".join(sv["citations"]) or "nothing",
            }
            for sv in verdict["subverdicts"]
        ],
        hide_index=True,
        width="stretch",
    )

    st.markdown("#### The reasoning behind each")
    for sv in verdict["subverdicts"]:
        sub = subclaims.get(sv["subclaim_id"], {})
        with st.expander(
            f"{sv['subclaim_id']} - {sv['verdict'].upper()} "
            f"({sv['confidence']:.0%}) - {sub.get('text', '')[:70]}"
        ):
            st.markdown(f"**Sub-claim:** {sub.get('text', '')}")
            st.caption(f"Would be proven false by: {sub.get('falsifier', 'n/a')}")
            st.markdown(f"**Why this verdict:** {sv['reasoning']}")
            st.warning(f"**Best argument against this ruling:** "
                       f"{sv['strongest_counter']}")
            if sv["citations"]:
                st.markdown("**Resting on:**")
                for c in sv["citations"]:
                    e = by_id.get(c)
                    if e:
                        st.markdown(
                            f"- `{c}` ({STANCE_MEANING.get(e['stance'], e['stance'])}) "
                            f"[{e['title'] or e['url']}]({e['url']})"
                        )
            else:
                st.markdown(
                    ":grey[Nothing. A verdict with no citation is automatically "
                    "downgraded to insufficient evidence and its confidence capped.]"
                )

    # --- evidence --------------------------------------------------------
    st.subheader("Evidence that survived")
    st.markdown(
        "Both agents drag back far more than this. The broker throws out anything "
        "irrelevant, removes duplicate sources, and scores what is left as "
        "**relevance x source tier**. Only the strongest few reach the judge, and "
        "they are renumbered `E1` upward so the judge cannot cite a source it "
        "never saw."
    )
    kept = sorted(evidence, key=lambda x: x["score"], reverse=True)
    st.caption(
        f"{len(state.get('graded', []))} sources graded this run, {len(kept)} kept."
    )

    for e in kept:
        with st.expander(
            f"{e['id']} - {e['stance'].upper()} - {(e['title'] or e['url'])[:80]}"
        ):
            st.markdown(f"[{e['url']}]({e['url']})")
            st.markdown(
                f"- **Stance:** {e['stance']} - {STANCE_MEANING.get(e['stance'], '')}\n"
                f"- **Relevance:** {e['relevance']:.2f} of 1.00, how directly it "
                f"bears on the claim\n"
                f"- **Source quality:** {TIER_MEANING.get(e['tier'], '')}\n"
                f"- **Score:** {e['score']:.2f} = relevance x tier, what ranked it\n"
                f"- **Found by:** the {e.get('found_by', '?')}, searching "
                f"*\"{e.get('query', '')}\"*"
            )
            st.caption(f"Broker's note: {e['reason']}")
            st.markdown("**What the page actually said:**")
            st.text(e["snippet"][:600])

    # --- open questions --------------------------------------------------
    if verdict.get("open_questions"):
        st.subheader("Still open")
        st.caption(
            "Gaps the judge named at the end. In an earlier round these become "
            "the leads the agents chase next."
        )
        for q in verdict["open_questions"]:
            st.markdown(f"- {q}")

    # --- run log ---------------------------------------------------------
    st.subheader("Run log")
    st.markdown(
        "What the audit cost and what the guardrails caught. These numbers are "
        "measured, not estimated - token counts come back from the API on every call."
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cost", f"${sum(t.get('usd', 0) for t in trace):.4f}",
              help="Real token counts, priced per model.")
    c2.metric("Searches", f"{state.get('searches_used', 0)} / {config.SEARCH_BUDGET}",
              help="A hard budget. When it runs out the debate stops.")
    c3.metric("Bad citations caught",
              sum(t.get("rejected_citations", 0) for t in trace),
              help="The judge cited a source that does not exist, or one that "
                   "argues the opposite way. Stripped before you saw it.")
    c4.metric("Confidence capped",
              sum(t.get("capped_confidences", 0) for t in trace),
              help="Wanted more than 70% confidence without two independent "
                   "credible sources, so it was capped.")

    tools_used = [t for entry in trace for t in entry.get("tools_used", [])]
    st.caption(
        f"Stopped because: **{state.get('stop_reason', 'n/a')}**  |  "
        f"tools the model chose to call: {', '.join(sorted(set(tools_used))) or 'none'}"
    )

    with st.expander("Every model call in this run"):
        st.caption(
            "One row per LLM call: which node made it, which model, how long it "
            "took, tokens in and out, and what it cost."
        )
        st.dataframe(trace, hide_index=True, width="stretch")

    st.download_button("Download the full report card", state.get("report", ""),
                       file_name="report_card.md",
                       help="Same report is also saved to the reports/ folder.")
