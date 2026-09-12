# Falsification Engine

Most LLM tools try to answer your question. This one tries to **destroy your claim**,
and only believes what survives.

Give it a claim, a paragraph, or a PDF. A prosecutor agent goes hunting for evidence
that kills it, a defender agent goes hunting for evidence that saves it, a broker
throws out the junk sources, and a judge rules — but the judge is not allowed to
assert anything it cannot cite. They argue in rounds until the verdict stops moving
or the search budget runs out.

You get back a credibility report card: a verdict per sub-claim, a confidence, the
evidence behind it, the strongest argument *against* the verdict, and what would
change its mind.

```
                    +-------------+
                    |  decompose  |   claim -> atomic sub-claims + falsifiers
                    +------+------+
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
                    |   broker    |   dedupe, grade, weight by source tier
                    +------+------+
                           v
                    +-------------+
                    |    judge    |   structured verdict, citations enforced
                    +------+------+
                           |
          settled? budget spent? round cap? ---- no ---> back to the debaters
                           |
                          yes
                           v
                    +-------------+
                    |   report    |   markdown + json report card
                    +-------------+
```

## Why it is built this way

**Opposed agents, not one balanced agent.** Ask one model to "weigh both sides" and it
writes a both-sides paragraph and moves on. Two agents with opposite, explicit jobs
actually go looking in different parts of the web, and the disagreement is real.

**The judge cannot cite what does not exist.** After the judge returns a verdict, every
citation is checked against the real evidence ids. Fabricated ones are stripped, and a
sub-verdict left with zero citations is forcibly downgraded to `insufficient evidence`
with its confidence capped. The report card prints how many were rejected — this is the
number most demos quietly hide.

**The broker is a separate, non-arguing node.** Both debaters are motivated to drag in
anything vaguely on-topic. The broker grades relevance, multiplies by a domain
credibility tier (.gov/.edu/arxiv > wikipedia/reuters > random blog), and keeps only the
strongest few — with both stances guaranteed representation, so one loud side cannot
crowd out the other.

**Budgets are real.** Rounds, searches and an early-stop rule are enforced in code, not
hoped for in a prompt. The report card shows exactly what was spent.

## Running it

```bash
git clone https://github.com/<you>/falsification-engine.git
cd falsification-engine
pip install -r requirements.txt
cp .env.example .env          # add your OPENAI_API_KEY

streamlit run app.py                                   # the demo
python engine.py "Remote work reduces productivity"    # cli, prints the report card
python engine.py --vs "..."                            # agent vs a plain model call
python evaluate.py --claims claims-hard.json           # score it against known answers
```

Flags: `--big` and `--huge` swap in stronger models, `--judge <model>` upgrades only
the decisive call, `--bare` runs the no-agent control on its own.

Reports land in `reports/` as both markdown and json.

## Evaluation

`evaluate.py` runs the engine against claims whose answer is already known and scores
four things:

| metric | what it catches |
|--------|-----------------|
| verdict accuracy | does it land on the right call |
| citation integrity | does every verdict actually rest on real evidence |
| framing robustness | does the verdict survive the claim being asked in a leading, flattering way |
| calibration gap | is it more confident when right than when wrong |

### What the evals actually caught

The first eval run scored 33% and found two design defects that reading the code would
not have surfaced:

- *"Handwashing reduces disease transmission"* came back **contested**. The broker was
  reserving half its evidence slots for each stance, so when no real refutation existed
  it manufactured a both-sides picture out of scraps, and the judge believed it. Fixed:
  the minority stance now earns slots only when its evidence clears a quality bar, and
  the judge is shown the evidence *balance* (counts and average strength per side), not
  just the contents.
- *"There are exactly 4,382 blue cars in Oslo today"* came back **refuted**. The judge
  was treating absence of evidence as refutation. Nobody published a rebuttal to a
  number nobody measured. Fixed: `refuted` now requires evidence that positively
  contradicts the claim; an unaddressed claim is `insufficient evidence` however
  implausible it sounds.

Both fixes came from the scorecard, not from guessing. That loop is the point.

### Framing robustness

This is the metric worth pausing on. Every claim in `evals/claims.json`
has a `leading` variant that pushes hard for the wrong answer ("Surely you agree
handwashing does nothing?"). A sycophantic system agrees with whoever asked. This
engine's verdict is supposed to be identical either way, and the scorecard reports the
percentage of the time it held. Latest results: `evals/scorecard.md`.

## Layout

| file | what it holds |
|------|---------------|
| `config.py` | models, budgets, pricing, source credibility tiers |
| `schemas.py` | every structured output + the graph state |
| `tools.py` | web search, page fetch, retrieval over the user's own document |
| `engine.py` | prompts, the six nodes, the graph, the report card |
| `app.py` | Streamlit demo, streams the debate live |
| `evaluate.py` | the eval harness and scorecard |

## Built with

LangGraph (cyclic state machine, parallel branches, reducers, checkpointer),
LangChain structured output (Pydantic), Chroma + OpenAI embeddings for the optional
source document, DuckDuckGo for search, Streamlit for the demo.
