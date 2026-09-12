# Falsification Engine — the complete explanation

Everything about this project: what it does, how every piece works, every prompt,
every schema, every guardrail, what it scores, every problem hit along the way and
what fixed it. Written to be read by anyone, not just the person who wrote it.

---

## 1. The idea in one paragraph

Almost every LLM app answers your question. That is the problem. Ask a chatbot "is X
true?" and you get a confident, agreeable paragraph, with no way to tell whether it
checked anything or simply recited something plausible. This project inverts that. You
give it a claim and it **attacks** the claim. One agent is paid to destroy it, another
is paid to save it, a third audits the sources both of them drag back, and a judge
rules on what survives — and the judge is not allowed to assert anything it cannot
cite. The output is a credibility report card: a verdict, a confidence, the evidence
behind it, the best argument *against* the verdict, and what would change its mind.

The name comes from Karl Popper: a claim is only worth anything if you can say what
evidence would prove it wrong. So every sub-claim the engine produces must arrive with
its own falsifier.

---

## 2. Why it is built this way

**Why two opposed agents instead of one balanced one.** Ask a single model to "weigh
both sides" and it writes a both-sides paragraph and stops. It does not go looking in
different places, and it has no incentive to find the thing that would embarrass the
claim. Two agents with opposite, explicit, non-negotiable jobs behave differently: the
prosecutor is forbidden from writing a query designed to confirm the claim, so it hunts
retractions, failed replications and dissent. The defender is forbidden from writing
one designed to undermine it. They end up in genuinely different parts of the web, and
the disagreement between them is real rather than performed.

**The lesson that shaped everything else.** An adversarial searcher will *always* find
something. Point an agent at "prove handwashing does not work" and it comes back with
*something*. So the integrity of the system does not live in the search. It lives in
the **filter between search and judgment** — the broker that audits sources, and the
rules in code that constrain what the judge may conclude from them. Almost every bug
in section 10 is a variation on that one theme.

**Why guardrails are code, not prompts.** A prompt is a request. Code is a guarantee.
The judge is *asked* to reason well; it is *prevented* from citing a source that does
not exist, from citing one that argues the opposite way, from claiming 90% confidence
on a single blog, and from returning an overall verdict its own sub-verdicts do not
support. Section 6 lists all eight.

---

## 3. The pipeline

```
                    +-------------+
                    |  decompose  |   claim -> atomic sub-claims + falsifiers
                    +------+------+   may call the clock
                           |
              +------------+------------+
              v                         v
      +---------------+        +---------------+
      |  prosecutor   |        |   defender    |   opposed search, in parallel
      | (refute only) |        | (support only)|
      +-------+-------+        +-------+-------+
              +------------+------------+
                           v
                    +-------------+
                    |   broker    |   dedupe, grade, audit the publisher,
                    +------+------+   score credibility, keep the strongest
                           v
                    +-------------+
                    |    judge    |   structured verdict, may call the clock,
                    +------+------+   then eight code guardrails run
                           |
          settled? budget spent? round cap? ---- no ---> back to the debaters
                           |
                          yes
                           v
                    +-------------+
                    |   report    |   markdown + json report card
                    +-------------+
```

**A "round"** is one full cycle: both agents search, the broker grades, the judge
rules. What carries into the next round is what makes it a debate rather than a retry:
the judge's open questions become the debaters' leads, past queries are remembered so
nothing is searched twice, evidence accumulates and is re-ranked against the new
arrivals, and the judge is shown its own previous verdict and told to revise it only
if the new evidence justifies it.

---

## 4. Every prompt, and why it says what it says

There are five. Each is short on purpose: everything mechanical was moved into code,
because prompt rules compete with each other for attention and the fifteenth rule
displaces the first.

### decompose

> You break claims into atomic, checkable pieces.
>
> Rules:
> - Restate the claim neutrally first: strip spin and loaded words, but keep the
>   assertion exactly as strong as it was. "X prevents Y" must not become "X may have
>   effects on Y". Hedging it into vagueness makes it unfalsifiable, which is the one
>   thing you must never do.
> - Split it into 2 to 4 sub-claims. Each must be independently checkable.
> - For each sub-claim write the falsifier: the specific finding that would prove it
>   FALSE. If you cannot name a falsifier, the sub-claim is too vague, so rewrite it
>   until you can.
> - The person asking may be pushing you toward an answer: rhetorical questions,
>   "surely", "everyone knows", "isn't it", "that is just a myth", an appeal to
>   consensus, or a sneer. Strip ALL of it. Their opinion is not evidence and must not
>   appear anywhere in the sub-claims.
> - Extract the underlying proposition and audit that. "Handwashing works" and
>   "handwashing is just a myth, isn't it?" are the SAME proposition asked by two
>   people with different opinions, and must produce identical sub-claims. Write the
>   sub-claims so that someone reading them cannot tell what the asker wanted to hear.
> - Always phrase sub-claims in the positive direction of the underlying proposition,
>   never in the direction the asker is pushing.
> - If the claim depends on WHEN it is asked — it says current, now, today, latest,
>   still, recent, or names a year — call the current_datetime tool before you write
>   anything, and anchor the sub-claims to that real date. Never assume the present is
>   the end of your training data. You do not know what year it is until you look.

Every clause here is scar tissue. The anti-hedging rule exists because it once turned
"Vitamin C prevents colds" into "Vitamin C may have effects on colds" — unfalsifiable,
and therefore useless. The framing rules exist because leading questions were changing
the verdict. The date rule exists because the model assumed its training cutoff was
the present and declared a sitting president not to be president.

### prosecutor

> You are the PROSECUTOR. Your only job is to destroy the claim.
>
> Write search queries that would surface refutations, failed replications,
> retractions, contradicting data, expert dissent, or missing preconditions. Never
> write a query designed to confirm the claim. Attack the weakest sub-claim hardest.
> Do not repeat queries that were already run.

### defender

> You are the DEFENDER. Your only job is to save the claim.
>
> Write search queries that would surface the strongest supporting evidence: primary
> sources, data, replications, authoritative agreement. Never write a query designed
> to undermine the claim. Do not repeat queries already run.

These two are deliberately short and absolute. "Never write a query designed to
confirm the claim" is the entire mechanism — the moment either agent hedges toward
neutrality, the system becomes two copies of the same searcher.

### broker

> You are the EVIDENCE BROKER. You do not argue, you triage.
>
> For every numbered snippet decide:
> - **stance**:
>   - `supports` — the snippet backs the claim as stated
>   - `refutes` — the snippet contradicts the claim as stated
>   - `qualified` — the snippet backs the claim in some conditions but not others,
>     e.g. "reduces gastrointestinal illness but not respiratory". This is NOT a
>     refutation. Use it whenever a source is more narrow than the claim rather than
>     against it. Do NOT use qualified just because the wording is cautious. Grade on
>     what the source CONCLUDES, not how hedged its summary reads. A government body
>     projecting job losses supports a claim about job losses even if the sentence
>     says "effects vary".
>   - `irrelevant` — it does not bear on the claim
> - **relevance**: 0 to 1, how directly it bears on the claim. Topical overlap is not
>   relevance. A snippet that merely mentions the topic is below 0.3.
> - **reason**: one short sentence.
>
> Be harsh. Marketing copy, SEO filler and vague gestures are irrelevant.
>
> You also audit WHO is speaking, because the domain name does not tell you:
> - **publisher**: what kind of body actually published this. Read the URL. A PDF on a
>   manufacturer's CDN is industry, whoever wrote it. A research institute that exists
>   to promote one treatment is advocacy, not academic.
> - **conflict**: does the publisher have a financial or ideological stake in this
>   subject, and is this document serving that stake? A homeopathy manufacturer or a
>   homeopathy research institute arguing that homeopathy works is
>   `arguing_own_interest`. The same body conceding that it does NOT work is
>   `arguing_against_own_interest`, which is rare and unusually strong. A statistics
>   agency with no position to protect is `none`. Judge what the source is DOING, not
>   how the claim happens to be phrased — the claim may be worded negatively, and that
>   must not confuse you.
> - **evidence_type**: what the document IS. A systematic review, a trial, a report, a
>   position paper, a press release. An organisation's summary of "the evidence" for
>   its own field is a position_paper, not a meta_analysis.
> - **retracted**: true if the title or text mentions retraction, withdrawal,
>   correction or an expression of concern. Look at the title carefully.
>
> Grade the document in front of you, not the reputation of the domain hosting it.
>
> Watch the dates. A snippet saying something became true on a date that has already
> passed SUPPORTS a present-tense claim.

That last instruction about dates fixed a real failure where a source saying "Trump is
the incumbent as of January 2025" was graded as *refuting* a present-tense claim,
because the model thought 2025 was still in the future.

### judge

> You are the JUDGE. You rule on evidence, not on plausibility.
>
> The evidence was gathered adversarially: one agent searched ONLY for refutations and
> one ONLY for support. How many sources sit on each side reflects how hard each agent
> searched, not the weight of the literature. Read what they say. Never count sides.
>
> Five rules:
>
> 1. Cite the evidence ids you relied on in the citations field. Any id you name in
>    your reasoning must appear there too.
> 2. "refuted" means the evidence positively contradicts the claim — a wrong date, a
>    debunked number, a finding of the opposite. Evidence that merely fails to
>    establish the claim is not a refutation.
> 3. "contested" means credible sources of comparable weight disagree about the same
>    question, and it is the right answer for questions researchers have argued over
>    for years. "insufficient evidence" means you could not find sources that speak to
>    the claim at all — not that you found a caveat alongside good evidence.
> 4. Weigh each source by the credibility score it carries. That score already
>    accounts for who published it, what kind of document it is, and whether they
>    profit from the answer. A 0.4 advocacy page does not offset a 3.0 meta-analysis,
>    however confidently it is written.
> 5. strongest_counter is the best case AGAINST your own verdict. If you cannot write
>    one, your confidence is too high.
>
> Confidence reflects the quality and agreement of the evidence, not how certain your
> sentence sounds. Today's date is given above: judge every date against it, never
> against what you remember being current.

This prompt was once forty lines and fifteen rules, accumulated one bug at a time.
They began interfering — the judge started returning an overall verdict that
contradicted its own sub-verdicts. Everything mechanical moved into code and the
prompt went back to five rules.

### the baseline (the control)

> You are a fact checker. Rule on the claim you are given.
>
> Answer with one of: supported, refuted, contested, insufficient evidence. Give a
> confidence between 0 and 1, and a short paragraph of reasoning.

Deliberately plain — it is what someone would type if they had no agent. Dressing it
up would turn the experiment into *agent vs prompt engineering* instead of *agent vs
no agent*. It shares the four verdict options and the confidence scale so the numbers
are comparable, but gets no tools, no search, and no date.

---

## 5. Every schema

Every LLM call in this project returns a validated Pydantic object, never free text.
The class becomes a JSON schema sent to the model, so the `description=` strings are
literally instructions it reads, and `Literal` types make invalid answers impossible
rather than merely discouraged.

### Decomposition — what decompose returns

```python
class SubClaim(BaseModel):
    id: str                 # short id like S1, S2
    text: str               # one atomic, checkable statement
    falsifier: str          # what evidence would prove this false

class Decomposition(BaseModel):
    subclaims: list[SubClaim]
    reframed: str           # the claim restated neutrally, no loaded words
```

### SearchPlan — what each debater returns

```python
class SearchPlan(BaseModel):
    queries: list[str]      # web search queries, 3 to 5 words each
```

### EvidenceGrade — what the broker returns per source

```python
class EvidenceGrade(BaseModel):
    evidence_id: str
    stance: Literal["supports", "refutes", "qualified", "irrelevant"]
    relevance: float = Field(ge=0, le=1)
    reason: str

    publisher: Literal["government", "academic", "journal", "news",
                       "encyclopedia", "advocacy", "industry",
                       "personal", "unknown"]
    conflict: Literal["none", "arguing_own_interest",
                      "arguing_against_own_interest"]
    evidence_type: Literal["meta_analysis", "trial", "observational", "report",
                           "position_paper", "press_release", "news_article",
                           "unknown"]
    retracted: bool
```

The bottom four fields are the source audit. Note `conflict` asks for **one**
judgement — "is this source serving its own interest here?" — rather than asking for a
direction that code then has to combine with the stance. An earlier version did the
latter, misread a negated claim, and turned a 0.3× penalty into a 1.3× bonus.

### Verdict — what the judge returns

```python
class SubVerdict(BaseModel):
    subclaim_id: str
    verdict: Literal["supported", "refuted", "contested", "insufficient evidence"]
    confidence: float = Field(ge=0, le=1)
    reasoning: str
    citations: list[str]        # evidence ids like E3 that back this
    strongest_counter: str      # the best argument against this verdict

class Verdict(BaseModel):
    subverdicts: list[SubVerdict]
    overall_verdict: Literal["supported", "refuted", "contested",
                             "insufficient evidence"]
    overall_confidence: float = Field(ge=0, le=1)
    what_would_change_my_mind: str
    open_questions: list[str]
```

### DirectVerdict — the baseline's output

```python
class DirectVerdict(BaseModel):
    verdict: Literal["supported", "refuted", "contested", "insufficient evidence"]
    confidence: float = Field(ge=0, le=1)
    reasoning: str
```

### State — the graph's memory

```python
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
```

**Why TypedDict here and Pydantic above.** The dividing line is trust. The LLM is an
untrusted source crossing into the system, so its output is validated. The state is
written only by our own node functions, gets copied and serialised at every step, and
receives partial updates — so it is a plain dict with type hints, no validation
overhead, and `total=False` makes every key optional. You can see the boundary in one
line of `decompose`: `[s.model_dump() for s in out.subclaims]` — Pydantic at the edge,
dicts inside.

---

## 6. Every guardrail, all enforced in code

Prompts ask. These eight prevent. Each one is counted and printed in the report card.

**1. Fabricated citations are stripped.** Every cited id is checked against the real
evidence list. Invented ones are deleted and counted. On a 24-run eval this fired 58
times — roughly 2.4 invented citations per audit, none of which reached a reader.

**2. Citations must point the same way the verdict does.**

```python
ALIGNED = {
    "supported": {"supports", "qualified"},
    "refuted": {"refutes"},
    "contested": {"supports", "refutes", "qualified"},
    "insufficient evidence": {"supports", "refutes", "qualified"},
}
```

The judge once cited a Lancet meta-analysis showing a 17% *reduction* as evidence
*against* the claim. Citing a supporting source for a refutation is not a citation, it
is a mistake, and it is rejected exactly like an invented id.

**3. Prose citations are salvaged.** The model often names its sources in the
reasoning text and leaves the citations field empty. Rather than throw out a
well-reasoned verdict over a formatting slip, ids are recovered from the prose with a
regex — then checked by rules 1 and 2, so nothing invented survives the salvage.

**4. No citation, no verdict.** A sub-verdict left with zero valid citations is
forcibly downgraded to `insufficient evidence` with its confidence capped at 0.3.

**5. Confidence has to be paid for.** Above 0.7 requires at least two *independent*
credible sources, deduplicated by URL — one outlet repeating itself is not two sources
agreeing.

**6. The whole is never more certain than its most certain part.** Overall confidence
is clamped to the highest sub-verdict confidence.

**7. The overall verdict must follow from the parts.** If the judge returns an overall
verdict that appears in none of its own sub-verdicts, it is overruled and derived
instead: all-insufficient stays insufficient, supported-plus-refuted becomes
contested, otherwise the most common sub-verdict wins, with confidence capped at 0.6.

**8. Retracted sources are dropped entirely.** Not down-weighted — removed. A retracted
paper is not weak evidence, it is withdrawn evidence. One run dropped three.

Plus two budget rules: a hard search budget, and an early stop when confidence stops
moving.

---

## 7. How a source is weighed

This began as a hardcoded domain list — `.gov` and `nature.com` score 3, Wikipedia 2,
everything else 1 — and that design failed in both directions. It let a homeopathy
manufacturer's PDF onto the same panel as the NIH, because nobody thinks to add
`cdn.boironusa.com` to a list. And it capped **The Lancet at 1.2** because
`thelancet.com` was not on the list either. A list can only ever describe the *domain*.
It cannot tell you that this particular article was retracted, or that this PDF is
marketing.

So the broker now audits the document, and the score is computed from that:

```python
def credibility(tier, publisher, evidence_type, conflict):
    if publisher == "unknown":
        score = float(tier)                     # fall back to the domain list
    else:
        score = float(PUBLISHER_CEILING[publisher])
        if tier >= 2:                           # the list agrees it is reputable
            score = max(score, float(tier))

    score *= EVIDENCE_WEIGHT[evidence_type]

    if conflict == "arguing_own_interest":
        score *= 0.3
    elif conflict == "arguing_against_own_interest":
        score *= 1.3

    return round(min(score, 3.0), 2)
```

| publisher | ceiling | | document type | weight |
|---|---|---|---|---|
| government, academic, journal | 3 | | meta-analysis | 1.2 |
| encyclopedia, news | 2 | | trial | 1.1 |
| advocacy, industry, personal | 1 | | observational | 1.0 |
| unknown | domain list | | report | 0.9 |
| | | | news article | 0.8 |
| | | | **position paper** | **0.5** |
| | | | **press release** | **0.4** |

Final weight is `credibility × relevance`, and that is what ranks the evidence.

**The conflict rule cuts both ways**, which is the part worth understanding. A
homeopathy manufacturer arguing that homeopathy works scores **0.36**. The same
manufacturer *conceding that it does not work* scores **1.17** — over three times
more — because nobody argues against their own interest without reason. That is an
admission against interest, and it is treated as unusually strong evidence.

For comparison: a Cochrane meta-analysis with no stake scores **3.0**, an NIH report
**2.7**, an advocacy position paper pushing its own field **0.36**.

A dissenting source must clear **1.5** to earn a reserved seat on the panel, which is
what keeps industry material off it without silencing genuine minority views.

---

## 8. The LangChain and LangGraph techniques, explained simply

**Why LangGraph and not a chain.** A chain is a straight line: `prompt | model |
parser`. This system needs to go *backwards* — judge back to the debaters for another
round — and needs two nodes running at once. That is a graph with cycles, which is
what LangGraph adds on top of LangChain. Everything below the graph layer is ordinary
LangChain: prompts, models, structured output, tools, retrievers, `.invoke()`.

**Nodes are plain functions: dict in, dict out.** Every node receives the *whole*
state and returns only the keys it changed. That is why the judge can read evidence
the broker gathered without anyone passing it along.

**Reducers.** The subtle part. If two nodes run in parallel and both write the same
key, LangGraph refuses rather than silently picking a winner — unless you say how to
combine them:

```python
raw_evidence: Annotated[list[dict], operator.add]   # both branches append
searches_used: Annotated[int, operator.add]         # both branches add
evidence: list[dict]                                # only the broker writes this
```

**Conditional edges.** Branching is a function returning a node name — and returning a
*list* of names runs them in parallel:

```python
def route(state):
    if stop_reason(state):
        return "report"
    return ["prosecutor", "defender"]
```

**Structured output.** `llm.with_structured_output(Verdict, include_raw=True)` returns
both the parsed object and the raw message, and the raw message carries
`usage_metadata` — the real token counts behind every cost figure in the report.

**Tool calling, and when to use it.** The rule this project settled on: *give the model
a tool when the need is unpredictable; call it directly when the need is structural.*
`web_search` is structural — the prosecutor node **is** "go search for refutations", so
the node calls it and the model only decides *what* to search for. `current_datetime`
is conditional: most claims do not need the date, some collapse without it, and only
the model can tell which. So it is bound to the model:

```python
talker = llm.bind_tools(allow_tools)
ai = talker.invoke(messages)
for call in ai.tool_calls:
    answer = by_name[call["name"]].invoke(call["args"])
    messages.append(ToolMessage(content=answer, tool_call_id=call["id"]))
# then the structured call runs on the unbound model, with the tool result in context
```

Binding happens per call, not globally — `bind_tools` and `with_structured_output` both
use the same underlying API, so binding tools *and* a response schema to one object
makes them compete. Two phases avoids the collision.

**Checkpointer.** The graph compiles with `InMemorySaver`, so every step is saved under
a thread id. That is what makes a run inspectable and what a human-in-the-loop pause
would attach to.

**RAG, optionally.** Upload a PDF or paste a URL and the text is split, embedded, and
put in a Chroma collection so both debaters can quote the document itself alongside
the web.

---

## 9. The files

| file | lines | what it holds |
|------|-------|---------------|
| `config.py` | ~130 | models, budgets, pricing, credibility model, all tunables |
| `schemas.py` | ~100 | every structured output plus the graph state |
| `tools.py` | ~100 | the clock, web search, page fetch, retrieval over your document |
| `engine.py` | ~770 | prompts, six nodes, guardrails, the graph, the report card |
| `app.py` | ~380 | Streamlit demo, streams the debate live, explains every score |
| `evaluate.py` | ~300 | eval harness, baseline, scorecards, comparisons |

Everything tunable lives in `config.py`, so you never hunt through the engine to change
a budget or a weight.

---

## 10. What it scores, and against what

`evaluate.py` runs the engine against claims whose answers are already known and
measures five things. Accuracy alone would be a poor grade, because a system can be
right for terrible reasons.

| metric | what it catches |
|--------|-----------------|
| **verdict accuracy** | does it land on the known-correct call |
| **citation integrity** | of the verdicts that made a call, how many rest on real, aligned evidence |
| **framing robustness** | does the verdict survive the claim being asked in a leading way |
| **calibration gap** | is it more confident when right than when wrong (negative is an alarm) |
| **stability** | do repeated runs of the same claim agree (below 100% means single-run results are partly noise) |

There are two claim sets and a control.

**`claims.json`** — 12 timeless, well-known claims: vaccines and autism, the Great
Wall from space, blue cars in Oslo. **`claims-hard.json`** — 20 claims across 10
categories, each designed so that recall alone cannot solve it: date arithmetic,
current facts, stale consensus, compound claims with one false half, magnitude traps,
absolute quantifiers, genuinely contested questions, and the unknowable.

**The baseline** is the same claims put to a strong model in one call, no agent. Every
claim also has a `leading` twin that pushes hard for the wrong answer, so sycophancy is
measured rather than assumed.

---

## 11. Results

### On easy, well-known claims, the agent loses

| | agent `4o-mini` | baseline `gpt-4.1` |
|---|---|---|
| accuracy | 75% | **92%** |
| cost per audit | $0.0046 | **$0.0011** |
| latency | 79s | **1s** |
| calibration gap | **+17%** | −13% |

A strong model recites textbook facts perfectly and instantly. Building an agent for
those is wasted effort. But note the baseline's calibration: **91% confident when
wrong** versus 88% when right. Wrong, fast, and certain.

### On claims that require checking, it wins decisively

| | baseline | agent `4o-mini` | agent `4.1-mini` |
|---|---|---|---|
| accuracy | 50% | 50% | **75%** |
| date arithmetic | **0/6** | 3/6 | **6/6** |
| current facts | 0/1 | 1/1 | 1/1 |
| citation integrity | 0% | 100% | 100% |
| calibration gap | −3% | +5% | **+6%** |

The baseline is perfect on everything it memorised and **zero on everything requiring
a clock**. The agent wins exactly the categories it was built for, including the two
unanswerable claims the baseline ruled on confidently.

### The model upgrade only pays off on hard problems

`gpt-4o-mini` → `gpt-4.1-mini` bought **+0%** on the easy set for 2.8× the cost, and
**+25 points** on the hard set. The gain landed precisely where the failure analysis
predicted: date arithmetic went 3/6 → 6/6, because those failures were *subtraction*
errors, not knowledge errors.

### What it still gets wrong

Framing robustness sits at **45%**, below the baseline's 70% — a leading question
changes the search queries, so the two runs see different evidence. `contested` remains
the weakest verdict. And the stronger model is *more* willing to rule on unanswerable
claims: better reasoning, worse epistemic humility.

---

## 12. Problems hit, and what fixed them

The honest build log. Several of these are mistakes in the *measurement*, not the
system — which is itself the lesson.

**1. Unknown state keys.** Nodes returned keys the `State` TypedDict did not declare;
LangGraph rejects those. Declared them, with reducers where two nodes write.

**2. The routing function's writes vanished.** A conditional edge only *reads* state to
pick a path; anything it mutates is discarded. Moved to a pure `stop_reason(state)`
helper that both the router and the report call.

**3. The neutral restatement destroyed the claim.** "Vitamin C prevents colds" became
"may have effects on colds" — unfalsifiable, so untestable. The prompt now demands the
assertion keep its original strength.

**4. One source counted three times.** The dedupe key included the snippet, so the same
paper surfaced three times with different snippet text and took three of nine evidence
slots. Dedupe on URL alone.

**5. Misleading stop reason.** Reported "budget spent" when the confidence had also
settled. Settled is now checked first because it is the informative reason.

**6. The broker manufactured false balance.** It reserved *half* the evidence slots for
each stance, so when no real refutation existed it filled them with scraps and the
judge called it contested. The system was inventing controversy. Fixed: rank by score,
and the minority side earns slots only by clearing a quality bar.

**7. Absence of evidence read as refutation.** "There are exactly 4,382 blue cars in
Oslo" came back *refuted*. Nobody publishes a rebuttal to a number nobody measured.
`refuted` now requires evidence that positively contradicts.

**8. Binary stance crushed nuance.** Sources saying "reduces gastrointestinal illness
but not respiratory" had to be filed as refutations. Added the `qualified` stance.

**9. The judge reasoned from source counts.** Because one agent searches only for
refutations, counts measure search effort, not the literature. The judge is now told
exactly how the evidence was sampled and forbidden to count sides.

**10. Confidence was free.** Nothing stopped 90% on one thin source. Added the
calibration guard; the gap went from −45% to −10% immediately.

**11. Our own metric was wrong.** Citation integrity "dropped" to 62%, but it was
counting an honest `insufficient evidence` refusal as a citation failure — punishing
the engine for being correct. **The measurement was the bug**, and trusting the number
would have meant "fixing" right behaviour.

**12. Citations pointing the wrong way were accepted.** We checked that a cited id
*existed*, never that it *agreed*. Added stance alignment.

**13. The minority slot was a loophole.** It let a 0.50-relevance SEO blog sit beside
the Lancet, because it was the only dissenting voice available. Dissent must now be
credible to hold a reserved seat.

**14. Nothing told the judge that source quality outranks source count.** Tiers were
computed and displayed but never explained to it.

**15. Gaps in the evidence ids invited guessing.** The judge saw E1, E2, E4, E9, E13 —
a list full of holes — and cited E5, which it had never seen. Those were stripped as
fabricated, leaving verdicts with no citations, which were then downgraded. The
guardrail was working perfectly on a problem we had created. Fixed by renumbering the
kept evidence contiguously. **The model was not being careless; the interface was bad.**

**16. The engine did not know what day it was.** Asked whether Trump is the current US
president, it answered **refuted at 100% confidence**, having restated the claim "as of
October 2023" — its own training cutoff. Every component then worked correctly on a
wrong clock: the broker graded "Trump is the incumbent as of January 2025" as a
*refutation*, because relative to 2023 that had not happened. Fixed with a
`current_datetime` tool the model calls when it decides it needs to, threaded through
state to every downstream node. The verdict became **supported at 70%**.

**17. Two Wikipedia pages counted as two independent sources.** The confidence guard
deduplicated by URL, so two articles on one site cleared the "two independent sources"
bar and allowed 100% confidence.

**18. The domain list failed in both directions.** It let `cdn.boironusa.com` — a
homeopathy manufacturer's CDN — weigh against the NIH, and capped The Lancet at 1.2
because `thelancet.com` was not on the list. Replaced with the per-document audit in
section 7.

**19. A conflict direction I made the code derive.** The first version asked the model
whether the publisher benefited if the claim were *true or false*, then combined that
with the stance. On a negated claim the model got the direction backwards, and a 0.3×
penalty became a 1.3× bonus — a 4.3× swing from one misread. Fixed by asking for one
judgement — "is this source serving its own interest here?" — instead of a direction
plus arithmetic.

**20. The judge cited in prose and left the field empty.** Its reasoning read "Sources
E1 and E3 explicitly state…" while `citations` was `[]`, so the no-citation rule
correctly downgraded a well-reasoned verdict. Added the salvage in guardrail 3.

**21. The judge prompt collapsed under its own weight.** After fifteen accumulated
rules it began returning an overall verdict contradicting its own sub-verdicts. Rules
moved into code; the prompt went back to five.

**22. Tuning on a single run.** The same claim came back refuted, then insufficient,
then contested, with nothing changed. Run-to-run variance was larger than the effects
being claimed — so some of the "fixes" and "regressions" above were probably neither.
Added `--trials N` with majority voting and a stability metric.

---

## 13. Known limitations

- **Only search snippets are read**, not full articles. Some grading errors trace
  directly to judging a paper by its 600-character abstract.
- **The broker is an LLM grading evidence for another LLM**, and its stance labels are
  where the pipeline is most fragile.
- **`contested` is still the weakest verdict**, and framing robustness is below the
  baseline's.
- **The eval sets are small** — 12 and 20 claims. They catch structural bugs, which is
  what they are for, but they are not benchmarks.
- **DuckDuckGo has no academic index.** PubMed and arXiv as first-class tools would
  help more than any prompt change.
- **Two time-sensitive eval rows** will need re-labelling as the world moves on.
- **No human-in-the-loop pause yet**, though the checkpointer is already in place.

---

## 14. Running it

```bash
pip install -r requirements.txt
cp .env.example .env          # add your OPENAI_API_KEY

streamlit run app.py                                  # the demo
python engine.py "your claim"                         # cli report card
python engine.py --bare "your claim"                  # the no-agent control
python engine.py --vs "your claim"                    # both, side by side
python evaluate.py --claims claims-hard.json          # score it
python evaluate.py --trials 3 --only H11,H18          # majority voting
python evaluate.py --compare A B C                    # compare runs
```

`--fast`, `--big` and `--huge` swap models; `--judge <model>` upgrades only the
decisive call. Deployment uses Streamlit secrets for the key, with an optional password
gate and a demo mode that caps what one visitor can spend.

---

## 15. The short version, if someone asks

> I built an adversarial fact-checking agent — prosecutor, defender, broker, judge, in
> a cyclic LangGraph. The interesting part is that I also wrote an eval harness and a
> no-agent control, and the control **beat** my agent 92% to 75% on well-known claims,
> at a quarter the cost and a fraction of the time. So I built a second eval set where
> the answer could not be recalled, only checked — and there the agent won 75% to 50%,
> with the plain model scoring **zero out of six** on anything requiring today's date.
> That is the actual finding: the machinery is worth its cost exactly when the answer
> is not already in the model's weights. Along the way the evals found design flaws I
> would never have caught by reading code — a broker manufacturing fake controversy, a
> judge treating absence of evidence as refutation, and an industry-funded PDF
> outweighing the NIH. The fixes are enforced in code rather than requested in prompts,
> because a prompt is a request and code is a guarantee.

That is a story about measuring your own work and being wrong in public, which is the
job.
