"""Scores the engine against claims whose answer we already know.

Four things are measured, not just accuracy:

  verdict accuracy    does it land on the right call
  citation integrity  does every verdict actually rest on real evidence
  framing robustness  does the verdict survive the claim being asked in a
                      leading, flattering way (an agreeable judge is useless)
  calibration         is it more confident when it is right than when it is wrong

run with:
  python evaluate.py                          full run on the default model
  python evaluate.py --quick                  first 3 claims, no framing runs
  python evaluate.py --model gpt-4.1-mini     run every role on another model
  python evaluate.py --claims claims-hard.json     run the hard set instead
  python evaluate.py --only H7,H11,H18        run just those claims
  python evaluate.py --trials 3               3 runs per claim, majority verdict
  python evaluate.py --compare A B            write a report comparing two runs

Each run writes evals/results-<tag>.json and evals/scorecard-<tag>.md, so runs
on different models do not overwrite each other.
"""

import json
import statistics
import sys
import time
from collections import Counter
from datetime import datetime

import config
import engine


def flag(args, name, fallback=None):
    return args[args.index(name) + 1] if name in args else fallback


def run_one(claim):
    """One audit, flattened into the numbers we care about."""
    start = time.time()
    state = engine.run(claim)
    verdict = state["verdict"]
    trace = state.get("trace", [])
    subverdicts = verdict["subverdicts"]

    return {
        "claim": claim,
        "verdict": verdict["overall_verdict"],
        "confidence": verdict["overall_confidence"],
        # only sub-verdicts that actually made a call can be expected to cite;
        # "insufficient evidence" citing nothing is the correct behaviour
        "decided": sum(1 for sv in subverdicts if sv["verdict"] != "insufficient evidence"),
        "cited": sum(1 for sv in subverdicts
                     if sv["verdict"] != "insufficient evidence" and sv["citations"]),
        "subverdicts": len(subverdicts),
        "capped": sum(t.get("capped_confidences", 0) for t in trace),
        "rejected_citations": sum(t.get("rejected_citations", 0) for t in trace),
        "tools_used": [t for entry in trace for t in entry.get("tools_used", [])],
        "rounds": state.get("round_no", 1) - 1,
        "stop_reason": state.get("stop_reason"),
        "usd": round(sum(t.get("usd", 0) for t in trace), 5),
        "seconds": round(time.time() - start, 1),
    }


def run_baseline(claim, model):
    """No graph, no search, no debate. One structured call to a strong model."""
    start = time.time()
    out, trace = engine.run_direct(claim, model)

    return {
        "claim": claim,
        "verdict": out.verdict,
        "confidence": out.confidence,
        # a baseline has no evidence, so it can cite nothing. That is the finding,
        # not a bug: it is being scored on exactly what it can actually produce.
        "decided": 1 if out.verdict != "insufficient evidence" else 0,
        "cited": 0,
        "subverdicts": 1,
        "capped": 0,
        "rejected_citations": 0,
        "tools_used": [],
        "rounds": 0,
        "stop_reason": "single call",
        "usd": trace["usd"],
        "seconds": round(time.time() - start, 1),
    }


def run_trials(claim, times, runner):
    """Run the same claim several times and take the majority verdict.

    One run tells you very little: the same claim can come back refuted, then
    insufficient, then contested, with nothing changed. Anything measured from a
    single run is as likely to be variance as signal.
    """
    runs = [runner(claim) for _ in range(times)]
    if times == 1:
        runs[0].update(trials=1, agreement=1.0, all_verdicts=[runs[0]["verdict"]])
        return runs[0]

    verdicts = [r["verdict"] for r in runs]
    winner, count = Counter(verdicts).most_common(1)[0]
    picked = [r for r in runs if r["verdict"] == winner]

    row = dict(picked[0])
    row["verdict"] = winner
    row["confidence"] = statistics.mean(r["confidence"] for r in picked)
    row["trials"] = times
    row["agreement"] = count / times        # 1.0 = it said the same thing every time
    row["all_verdicts"] = verdicts
    # cost and time are what the whole exercise actually took
    row["usd"] = round(sum(r["usd"] for r in runs), 5)
    row["seconds"] = round(sum(r["seconds"] for r in runs), 1)
    for key in ("capped", "rejected_citations"):
        row[key] = sum(r[key] for r in runs)
    return row


def measure(rows):
    """Turn a pile of runs into the handful of numbers that matter."""
    neutral = [r for r in rows if r["kind"] == "neutral"]
    framed = [r for r in rows if r["kind"] == "leading"]
    correct = [r for r in neutral if r["correct"]]
    wrong = [r for r in neutral if not r["correct"]]
    decided = sum(r["decided"] for r in rows) or 1

    conf_right = sum(r["confidence"] for r in correct) / len(correct) if correct else 0
    conf_wrong = sum(r["confidence"] for r in wrong) / len(wrong) if wrong else 0

    return {
        "runs": len(rows),
        "accuracy": len(correct) / len(neutral) if neutral else 0,
        "integrity": sum(r["cited"] for r in rows) / decided,
        "robustness": (sum(1 for r in framed if r["held_framing"]) / len(framed)
                       if framed else None),
        "rejected": sum(r["rejected_citations"] for r in rows),
        "capped": sum(r["capped"] for r in rows),
        "tool_calls": sum(len(r["tools_used"]) for r in rows),
        "conf_right": conf_right,
        "conf_wrong": conf_wrong,
        "gap": conf_right - conf_wrong,
        "stability": (statistics.mean(r.get("agreement", 1.0) for r in rows)
                      if rows else 1.0),
        "cost": sum(r["usd"] for r in rows),
        "avg_cost": sum(r["usd"] for r in rows) / max(len(rows), 1),
        "avg_seconds": sum(r["seconds"] for r in rows) / max(len(rows), 1),
        "total_minutes": sum(r["seconds"] for r in rows) / 60,
    }


def main():
    args = sys.argv[1:]
    quick = "--quick" in args
    baseline = flag(args, "--baseline")
    model = baseline or flag(args, "--model", config.FAST_MODEL)
    tag = flag(args, "--tag", ("baseline-" + model) if baseline else model)

    # one model for every role, so the comparison is apples to apples
    config.FAST_MODEL = config.JUDGE_MODEL = model

    claims_file = flag(args, "--claims", "claims.json")
    cases = json.loads(
        (config.EVALS_DIR / claims_file).read_text(encoding="utf-8"))
    if quick:
        cases = cases[:3]
    trials = int(flag(args, "--trials", 1))
    only = flag(args, "--only")          # e.g. --only H7,H11,H18
    if only:
        wanted = {c.strip() for c in only.split(",")}
        cases = [c for c in cases if c["id"] in wanted]

    print(f"model: {model}  |  {len(cases)} claims  |  tag: {tag}\n")
    rows = []
    for case in cases:
        print(f"[{case['id']}] {case['claim'][:70]}")
        runner = (lambda c: run_baseline(c, model)) if baseline else run_one
        result = run_trials(case["claim"], trials, runner)
        result.update(id=case["id"], expected=case["expected"], kind="neutral",
                      category=case.get("category", "general"))
        result["correct"] = result["verdict"] == case["expected"]
        rows.append(result)
        spread = ("" if trials == 1 else
                  f"  [{result['agreement']:.0%} agreement across {trials}: "
                  f"{', '.join(result['all_verdicts'])}]")
        print(f"    -> {result['verdict']} (expected {case['expected']}) "
              f"{'ok' if result['correct'] else 'MISS'} "
              f"{result['seconds']}s ${result['usd']}{spread}")

        if not quick and case.get("leading"):
            lead = run_trials(case["leading"], trials, runner)
            lead.update(id=f"{case['id']}-lead", expected=case["expected"],
                        kind="leading", category=case.get("category", "general"))
            lead["correct"] = lead["verdict"] == case["expected"]
            lead["held_framing"] = lead["verdict"] == result["verdict"]
            rows.append(lead)
            print(f"    -> leading: {lead['verdict']} "
                  f"[{'held' if lead['held_framing'] else 'FLIPPED'}]")

    write_scorecard(rows, measure(rows), model, tag, quick, baseline=bool(baseline),
                    claims_file=claims_file)


def by_category(rows):
    """Accuracy per claim type. Where a system wins matters more than whether."""
    groups = {}
    for r in rows:
        if r["kind"] == "neutral":
            groups.setdefault(r.get("category", "general"), []).append(r)
    return {k: (sum(1 for r in v if r["correct"]), len(v))
            for k, v in sorted(groups.items())}


def write_scorecard(rows, m, model, tag, quick, baseline=False, claims_file="claims.json"):
    how = ("**baseline**: one direct call per claim, no search, no tools, no debate"
           if baseline else f"the full agentic graph, every role on `{model}`")
    lines = [
        f"# Scorecard - `{model}`" + (" (baseline)" if baseline else ""),
        "",
        f"_{datetime.now():%Y-%m-%d %H:%M}_ - {m['runs']} runs"
        f"{' (quick)' if quick else ''}, {how}",
        "",
        f"Claim set: `{claims_file}`",
        "",
        "| metric | value | reading |",
        "|--------|-------|---------|",
        f"| verdict accuracy | {m['accuracy']:.0%} | lands on the known-correct call |",
        f"| citation integrity | {m['integrity']:.0%} | sub-verdicts that made a call and "
        f"cited real evidence for it"
        + (" - a baseline has no evidence, so this is 0 by construction |"
           if baseline else " |"),
    ]
    if m["robustness"] is not None:
        lines.append(f"| framing robustness | {m['robustness']:.0%} | verdict unchanged "
                     f"when the claim is asked in a leading way |")
    lines += [
        f"| confidence when right | {m['conf_right']:.0%} | |",
        f"| confidence when wrong | {m['conf_wrong']:.0%} | should be lower than the row above |",
        f"| calibration gap | {m['gap']:+.0%} | positive is good |",
        f"| fabricated citations rejected | {m['rejected']} | caught by the citation check |",
        f"| confidences capped | {m['capped']} | too thinly sourced for the confidence asked |",
        f"| tool calls made | {m['tool_calls']} | times the model reached for current_datetime |",
        f"| stability | {m['stability']:.0%} | how often repeated runs of the same "
        f"claim agreed. Below 100% means single-run results are partly noise |",
        f"| total cost | ${m['cost']:.4f} | |",
        f"| avg cost per audit | ${m['avg_cost']:.4f} | |",
        f"| avg latency | {m['avg_seconds']:.0f}s | |",
        "",
        "## Accuracy by claim type",
        "",
        "| category | correct | accuracy |",
        "|----------|---------|----------|",
    ]
    for cat, (hit, total) in by_category(rows).items():
        lines.append(f"| {cat} | {hit}/{total} | {hit / total:.0%} |")

    lines += [
        "",
        "## Per claim",
        "",
        "| id | claim | expected | got | conf | rounds | stopped | cost |",
        "|----|-------|----------|-----|------|--------|---------|------|",
    ]
    for r in rows:
        lines.append(
            f"| {r['id']} | {r['claim'][:55]} | {r['expected']} | "
            f"{r['verdict']} {'ok' if r['correct'] else 'MISS'} "
            f"| {r['confidence']:.0%} | {r['rounds']} | {r['stop_reason']} | ${r['usd']} |"
        )

    wrong = [r for r in rows if r["kind"] == "neutral" and not r["correct"]]
    if wrong:
        lines += ["", "## Misses worth looking at", ""]
        for r in wrong:
            lines.append(f"- **{r['id']}**: expected {r['expected']}, got {r['verdict']} "
                         f"at {r['confidence']:.0%} confidence")

    flipped = [r for r in rows if r.get("held_framing") is False]
    if flipped:
        lines += ["", "## Flipped under leading framing", ""]
        for r in flipped:
            lines.append(f"- **{r['id']}**: {r['verdict']} when asked leadingly")

    config.EVALS_DIR.mkdir(exist_ok=True)
    (config.EVALS_DIR / f"scorecard-{tag}.md").write_text("\n".join(lines), encoding="utf-8")
    (config.EVALS_DIR / f"results-{tag}.json").write_text(
        json.dumps({"model": model, "rows": rows}, indent=2), encoding="utf-8")

    print("\n" + "\n".join(lines[:22]))
    print(f"\nwrote evals/scorecard-{tag}.md")


def compare(*tags):
    """Any number of runs, side by side, plus where they disagree."""
    runs = []
    for tag in tags:
        data = json.loads(
            (config.EVALS_DIR / f"results-{tag}.json").read_text(encoding="utf-8"))
        runs.append({"tag": tag, "model": data["model"], "rows": data["rows"],
                     "m": measure(data["rows"])})

    def line(label, key, fmt, higher_better=True):
        vals = [r["m"][key] for r in runs]
        if any(v is None for v in vals):
            return f"| {label} |" + " - |" * len(runs) + " - |"
        pick = max(vals) if higher_better else min(vals)
        winners = [r["tag"] for r, v in zip(runs, vals) if v == pick]
        best = "tie" if len(winners) == len(runs) else ", ".join(winners)
        return f"| {label} | " + " | ".join(fmt(v) for v in vals) + f" | {best} |"

    pct = lambda v: f"{v:.0%}"
    num = lambda v: f"{v:g}"
    usd = lambda v: f"${v:.4f}"

    head = " | ".join(r["tag"] for r in runs)
    rule = "|".join(["--------"] * len(runs))

    lines = [
        "# Comparison",
        "",
        f"_{datetime.now():%Y-%m-%d %H:%M}_",
        "",
    ]
    for r in runs:
        lines.append(f"- **{r['tag']}** - `{r['model']}`, {r['m']['runs']} runs, "
                     f"${r['m']['cost']:.4f}, {r['m']['total_minutes']:.0f} min")
    lines += [
        "",
        f"| metric | {head} | best |",
        f"|--------|{rule}|------|",
        line("verdict accuracy", "accuracy", pct),
        line("citation integrity", "integrity", pct),
        line("framing robustness", "robustness", pct),
        line("calibration gap", "gap", lambda v: f"{v:+.0%}"),
        line("confidence when right", "conf_right", pct),
        line("confidence when wrong", "conf_wrong", pct, higher_better=False),
        line("fabricated citations rejected", "rejected", num, higher_better=False),
        line("confidences capped", "capped", num, higher_better=False),
        line("tool calls made", "tool_calls", num),
        line("avg cost per audit", "avg_cost", usd, higher_better=False),
        line("avg latency", "avg_seconds", lambda v: f"{v:.0f}s", higher_better=False),
        "",
        "## Accuracy by claim type",
        "",
        "This is the table that matters. Overall accuracy hides which system wins where.",
        "",
        f"| category | {head} |",
        f"|----------|{rule}|",
    ]

    cats = sorted({r.get("category", "general")
                   for run in runs for r in run["rows"] if r["kind"] == "neutral"})
    for cat in cats:
        cells = []
        for run in runs:
            got = by_category(run["rows"]).get(cat)
            cells.append(f"{got[0]}/{got[1]}" if got else "-")
        lines.append(f"| {cat} | " + " | ".join(cells) + " |")

    lines += ["", "## Where they disagreed", ""]
    indexed = [{r["id"]: r for r in run["rows"]} for run in runs]
    ids = [i for i in indexed[0]
           if all(i in ix for ix in indexed)
           and len({ix[i]["verdict"] for ix in indexed}) > 1]

    if ids:
        lines += [f"| id | expected | {head} | right |", f"|----|----------|{rule}|-------|"]
        for i in ids:
            cells = [f"{ix[i]['verdict']} ({ix[i]['confidence']:.0%})" for ix in indexed]
            right = [run["tag"] for run, ix in zip(runs, indexed) if ix[i]["correct"]]
            lines.append(f"| {i} | {indexed[0][i]['expected']} | " + " | ".join(cells)
                         + f" | {', '.join(right) or 'none'} |")
    else:
        lines.append("They returned the same verdict on every claim.")

    everyone_wrong = [i for i in indexed[0]
                      if all(i in ix and not ix[i]["correct"] for ix in indexed)
                      and indexed[0][i]["kind"] == "neutral"]
    if everyone_wrong:
        lines += ["", "## Wrong everywhere", "",
                  "No model choice fixes these. They are engine or evidence problems.", ""]
        for i in everyone_wrong:
            got = " / ".join(ix[i]["verdict"] for ix in indexed)
            lines.append(f"- **{i}** ({indexed[0][i].get('category', '')}): "
                         f"expected {indexed[0][i]['expected']}, got {got}")

    report = "\n".join(lines)
    (config.EVALS_DIR / "comparison.md").write_text(report, encoding="utf-8")
    print(report)
    print("\nwrote evals/comparison.md")


if __name__ == "__main__":
    if "--compare" in sys.argv:
        i = sys.argv.index("--compare")
        compare(*sys.argv[i + 1:])
    else:
        main()
