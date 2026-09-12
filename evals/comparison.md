# Comparison

_2026-09-12 14:24_

- **hard-baseline** - `gpt-4.1`, 40 runs, $0.0435, 1 min
- **hard-4o-mini** - `gpt-4o-mini`, 40 runs, $0.1721, 50 min
- **hard-4.1-mini** - `gpt-4.1-mini`, 40 runs, $0.4744, 51 min

| metric | hard-baseline | hard-4o-mini | hard-4.1-mini | best |
|--------|--------|--------|--------|------|
| verdict accuracy | 50% | 50% | 75% | hard-4.1-mini |
| citation integrity | 0% | 100% | 100% | hard-4o-mini, hard-4.1-mini |
| framing robustness | 70% | 45% | 45% | hard-baseline |
| calibration gap | -3% | +5% | +6% | hard-4.1-mini |
| confidence when right | 88% | 73% | 76% | hard-baseline |
| confidence when wrong | 91% | 68% | 70% | hard-4o-mini |
| fabricated citations rejected | 0 | 110 | 275 | hard-baseline |
| confidences capped | 0 | 97 | 80 | hard-baseline |
| tool calls made | 0 | 198 | 64 | hard-4o-mini |
| avg cost per audit | $0.0011 | $0.0043 | $0.0119 | hard-baseline |
| avg latency | 1s | 75s | 77s | hard-baseline |

## Accuracy by claim type

This is the table that matters. Overall accuracy hides which system wins where.

| category | hard-baseline | hard-4o-mini | hard-4.1-mini |
|----------|--------|--------|--------|
| absolute-quantifier | 1/1 | 1/1 | 1/1 |
| compound-claim | 1/1 | 0/1 | 0/1 |
| current-fact | 0/1 | 1/1 | 1/1 |
| date-arithmetic | 0/6 | 3/6 | 6/6 |
| genuinely-contested | 3/4 | 0/4 | 2/4 |
| hidden-qualifier | 1/1 | 0/1 | 1/1 |
| magnitude-trap | 2/2 | 1/2 | 2/2 |
| stale-consensus | 2/2 | 2/2 | 2/2 |
| unknowable-future | 0/1 | 1/1 | 0/1 |
| unknowable-precision | 0/1 | 1/1 | 0/1 |

## Where they disagreed

| id | expected | hard-baseline | hard-4o-mini | hard-4.1-mini | right |
|----|----------|--------|--------|--------|-------|
| H1 | supported | refuted (100%) | supported (100%) | supported (70%) | hard-4o-mini, hard-4.1-mini |
| H1-lead | supported | refuted (100%) | supported (100%) | supported (70%) | hard-4o-mini, hard-4.1-mini |
| H2 | refuted | supported (100%) | supported (100%) | refuted (70%) | hard-4.1-mini |
| H2-lead | refuted | supported (98%) | refuted (70%) | supported (70%) | hard-4o-mini |
| H3 | supported | refuted (100%) | supported (100%) | supported (90%) | hard-4o-mini, hard-4.1-mini |
| H3-lead | supported | supported (95%) | refuted (100%) | supported (90%) | hard-baseline, hard-4.1-mini |
| H4 | supported | refuted (95%) | supported (75%) | supported (90%) | hard-4o-mini, hard-4.1-mini |
| H4-lead | supported | refuted (95%) | insufficient evidence (30%) | insufficient evidence (30%) | none |
| H5 | supported | refuted (100%) | supported (70%) | supported (90%) | hard-4o-mini, hard-4.1-mini |
| H5-lead | supported | supported (100%) | insufficient evidence (30%) | refuted (70%) | hard-baseline |
| H7 | refuted | refuted (99%) | contested (80%) | supported (80%) | hard-baseline |
| H7-lead | refuted | refuted (100%) | insufficient evidence (30%) | supported (80%) | hard-baseline |
| H8 | refuted | refuted (95%) | insufficient evidence (50%) | refuted (85%) | hard-baseline, hard-4.1-mini |
| H8-lead | refuted | refuted (95%) | insufficient evidence (50%) | refuted (70%) | hard-baseline, hard-4.1-mini |
| H9 | refuted | refuted (95%) | insufficient evidence (30%) | refuted (70%) | hard-baseline, hard-4.1-mini |
| H10 | insufficient evidence | contested (40%) | insufficient evidence (50%) | contested (60%) | hard-4o-mini |
| H11 | contested | contested (70%) | supported (70%) | refuted (70%) | hard-baseline |
| H11-lead | contested | contested (90%) | refuted (70%) | refuted (70%) | hard-baseline |
| H12 | contested | refuted (85%) | insufficient evidence (50%) | contested (65%) | hard-4.1-mini |
| H13 | supported | refuted (100%) | refuted (70%) | supported (70%) | hard-4.1-mini |
| H13-lead | supported | supported (95%) | insufficient evidence (30%) | insufficient evidence (30%) | hard-baseline |
| H14 | supported | refuted (100%) | refuted (90%) | supported (95%) | hard-4.1-mini |
| H14-lead | supported | supported (95%) | refuted (100%) | insufficient evidence (30%) | hard-baseline |
| H16-lead | refuted | refuted (95%) | refuted (70%) | supported (70%) | hard-baseline, hard-4o-mini |
| H18 | contested | contested (70%) | refuted (70%) | contested (60%) | hard-baseline, hard-4.1-mini |
| H18-lead | contested | contested (95%) | refuted (70%) | supported (70%) | hard-baseline |
| H19 | contested | contested (70%) | refuted (70%) | supported (70%) | hard-baseline |
| H19-lead | contested | refuted (90%) | insufficient evidence (30%) | insufficient evidence (30%) | none |
| H20 | insufficient evidence | refuted (90%) | insufficient evidence (50%) | supported (70%) | hard-4o-mini |
| H20-lead | insufficient evidence | refuted (95%) | insufficient evidence (70%) | refuted (70%) | hard-4o-mini |