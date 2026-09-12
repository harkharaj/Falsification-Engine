# Final Project — Candidate Ideas

Baseline already covered in this repo: prompts, chains, runnables (LCEL), structured
output, output parsers, loaders, splitters, embeddings, Chroma vector store, naive RAG,
custom `@tool` + tool calling.

The capstone should add what is NOT here yet, because that is what separates a course
repo from a portfolio piece:

- a real **state machine / graph** (LangGraph) with cycles, not a linear chain
- **multi-agent** roles that disagree with each other
- **memory + persistence** (checkpointer, resumable runs, human-in-the-loop)
- **evaluation** (a scored test suite, not vibes)
- **observability** (traces, token cost, latency per node)
- a **demo surface** (Streamlit/FastAPI) + README with architecture diagram

---

## 1. Falsification Engine  (adversarial claim auditor)   ⭐ recommended
Give it a claim, a blog post, a paper, or a tweet. Instead of "summarising" it, the system
tries to **destroy** it.

Graph: `Decompose` -> (`Prosecutor` || `Defender`) -> `Evidence broker` -> `Judge` -> loop
until the judge's confidence stops moving or the falsification budget is spent.

- Prosecutor agent: web search + retrieval, hunts for disconfirming evidence only.
- Defender agent: hunts supporting evidence only.
- Evidence broker: dedupes, scores source quality, refuses uncited assertions.
- Judge: structured Pydantic verdict -> claim, verdict, confidence, strongest counter-
  evidence, what would change my mind.
- Output: a "credibility report card" with per-sub-claim scoring and citations.

Why recruiters react: it is epistemics, not chat. Cyclic graph, role conflict, budget
control, citation enforcement, structured verdicts. Nobody's bootcamp repo has this.

## 2. Repo Archaeologist  (why does this code exist?)
Point it at a GitHub repo. It builds a **knowledge graph** (AST parse -> functions,
classes, imports as nodes/edges) and indexes git history + issues + PR discussion.
Then answers multi-hop questions a vector search cannot: "why was this retry added?",
"what breaks if I delete this?", "who owns this and what were they arguing about?"

Agentic multi-hop retrieval: graph traversal tool + vector tool + git blame tool, agent
decides which to call and when to stop.

Why recruiters react: it is a tool *they* would use, and graph + vector hybrid retrieval
is a genuinely senior technique.

## 3. Self-Improving Prompt Lab  (the agent that grades itself)
You hand it a chain and 5 example inputs. It:
1. auto-generates an eval set including adversarial/edge cases,
2. runs the chain, scores with an LLM-judge + programmatic checks,
3. clusters the failures into named failure modes,
4. writes candidate prompt patches, A/B tests them, keeps the winner,
5. commits a versioned prompt + a scorecard.

Why recruiters react: this is literally what an LLM engineer does at work. Shows you
understand evals and regression, which ~95% of portfolio projects skip.

## 4. Incident Commander  (SRE agent)
Ingest logs + runbooks + architecture docs. Feed it a synthetic incident. It builds a
**hypothesis tree**, ranks by prior, tests each with tools (log query, metric query,
config diff), prunes, escalates to a human when confidence is low, then writes the RCA
in a structured post-mortem format.

Why recruiters react: human-in-the-loop interrupt, explicit reasoning trace, and the
output is an artifact a real team would file.

## 5. Compliance Drift Detector
Two corpora: external regulation/policy docs, and the company's internal policies.
When the external doc changes, the agent diffs versions semantically, maps each changed
clause to the internal clauses it affects, and emits a remediation ticket per gap.

Why recruiters react: cross-corpus reasoning (two vector stores arguing), temporal diffs,
and an obvious B2B revenue story.

---

## Scoring

| # | Idea | Uniqueness | Difficulty | Demo appeal |
|---|------|-----------|-----------|-------------|
| 1 | Falsification Engine | very high | medium-high | very high |
| 2 | Repo Archaeologist | high | high | high |
| 3 | Self-Improving Prompt Lab | high | medium | medium-high |
| 4 | Incident Commander | medium-high | medium | high |
| 5 | Compliance Drift Detector | medium-high | medium | medium |
