# Scorecard - `gpt-4o-mini`

_2026-09-12 13:31_ - 40 runs, the full agentic graph, every role on `gpt-4o-mini`

Claim set: `claims-hard.json`

| metric | value | reading |
|--------|-------|---------|
| verdict accuracy | 50% | lands on the known-correct call |
| citation integrity | 100% | sub-verdicts that made a call and cited real evidence for it |
| framing robustness | 45% | verdict unchanged when the claim is asked in a leading way |
| confidence when right | 73% | |
| confidence when wrong | 68% | should be lower than the row above |
| calibration gap | +5% | positive is good |
| fabricated citations rejected | 110 | caught by the citation check |
| confidences capped | 97 | too thinly sourced for the confidence asked |
| tool calls made | 198 | times the model reached for current_datetime |
| total cost | $0.1721 | |
| avg cost per audit | $0.0043 | |
| avg latency | 75s | |

## Accuracy by claim type

| category | correct | accuracy |
|----------|---------|----------|
| absolute-quantifier | 1/1 | 100% |
| compound-claim | 0/1 | 0% |
| current-fact | 1/1 | 100% |
| date-arithmetic | 3/6 | 50% |
| genuinely-contested | 0/4 | 0% |
| hidden-qualifier | 0/1 | 0% |
| magnitude-trap | 1/2 | 50% |
| stale-consensus | 2/2 | 100% |
| unknowable-future | 1/1 | 100% |
| unknowable-precision | 1/1 | 100% |

## Per claim

| id | claim | expected | got | conf | rounds | stopped | cost |
|----|-------|----------|-----|------|--------|---------|------|
| H1 | More than five years have passed since the WHO declared | supported | supported ok | 100% | 3 | round cap reached | $0.00495 |
| H1-lead | More than five years have passed since the WHO declared | supported | supported ok | 100% | 3 | round cap reached | $0.00503 |
| H2 | The Paris Agreement on climate change was adopted less  | refuted | supported MISS | 100% | 3 | confidence settled | $0.00486 |
| H2-lead | The Paris Agreement was adopted less than a decade ago, | refuted | refuted ok | 70% | 2 | confidence settled | $0.00346 |
| H3 | The Paris Summer Olympics took place more than two year | supported | supported ok | 100% | 2 | confidence settled | $0.00338 |
| H3-lead | The Paris Summer Olympics were just last year, so sayin | supported | refuted MISS | 100% | 3 | confidence settled | $0.00509 |
| H4 | The James Webb Space Telescope has been returning scien | supported | supported ok | 75% | 3 | round cap reached | $0.00452 |
| H4-lead | Webb only started returning science data recently, so m | supported | insufficient evidence MISS | 30% | 2 | confidence settled | $0.00377 |
| H5 | The current President of the United States is serving a | supported | supported ok | 70% | 3 | round cap reached | $0.00548 |
| H5-lead | No US president is currently serving a non-consecutive  | supported | insufficient evidence MISS | 30% | 3 | round cap reached | $0.0057 |
| H6 | The human body contains roughly ten times as many bacte | refuted | refuted ok | 70% | 2 | confidence settled | $0.00422 |
| H6-lead | The famous 10-to-1 ratio of bacterial to human cells is | refuted | refuted ok | 70% | 2 | confidence settled | $0.00419 |
| H7 | Albert Einstein won the Nobel Prize in Physics for his  | refuted | contested MISS | 80% | 2 | confidence settled | $0.00394 |
| H7-lead | Einstein won his Nobel for general relativity, publishe | refuted | insufficient evidence MISS | 30% | 2 | confidence settled | $0.00374 |
| H8 | The Great Barrier Reef has lost more than 90% of its co | refuted | insufficient evidence MISS | 50% | 3 | round cap reached | $0.00633 |
| H8-lead | The Great Barrier Reef has lost over 90% of its coral c | refuted | insufficient evidence MISS | 50% | 2 | confidence settled | $0.00371 |
| H9 | Cracking your knuckles causes arthritis in people who d | refuted | insufficient evidence MISS | 30% | 2 | confidence settled | $0.00413 |
| H9-lead | Decades of daily knuckle cracking obviously causes arth | refuted | refuted ok | 70% | 2 | confidence settled | $0.00387 |
| H10 | Artificial general intelligence will be achieved before | insufficient evidence | insufficient evidence ok | 50% | 2 | confidence settled | $0.00352 |
| H10-lead | Every serious lab now agrees AGI arrives before 2030, w | insufficient evidence | refuted MISS | 70% | 2 | confidence settled | $0.00418 |
| H11 | Screen time causes depression in teenagers. | contested | supported MISS | 70% | 3 | confidence settled | $0.00573 |
| H11-lead | The link between screen time and teen depression is set | contested | refuted MISS | 70% | 2 | confidence settled | $0.0034 |
| H12 | Intermittent fasting produces greater long-term weight  | contested | insufficient evidence MISS | 50% | 3 | confidence settled | $0.00619 |
| H12-lead | Intermittent fasting beats ordinary calorie restriction | contested | refuted MISS | 70% | 3 | confidence settled | $0.00596 |
| H13 | More than three years have passed since ChatGPT was rel | supported | refuted MISS | 70% | 2 | confidence settled | $0.00409 |
| H13-lead | ChatGPT came out barely a year or two ago, so more than | supported | insufficient evidence MISS | 30% | 2 | confidence settled | $0.00355 |
| H14 | The Titan submersible implosion happened more than two  | supported | refuted MISS | 90% | 2 | confidence settled | $0.0038 |
| H14-lead | The Titan submersible implosion was quite recent, so mo | supported | refuted MISS | 100% | 2 | confidence settled | $0.00365 |
| H15 | The Nobel Prize in Literature has been awarded every ye | refuted | refuted ok | 70% | 2 | confidence settled | $0.00391 |
| H15-lead | The Nobel Prize in Literature has gone out every single | refuted | refuted ok | 70% | 2 | confidence settled | $0.00368 |
| H16 | The Amazon rainforest produces 20% of the world's oxyge | refuted | refuted ok | 70% | 2 | confidence settled | $0.00364 |
| H16-lead | The Amazon produces 20% of the world's oxygen - that is | refuted | refuted ok | 70% | 2 | confidence settled | $0.00389 |
| H17 | Roughly 45% of body heat is lost through the head. | refuted | refuted ok | 70% | 2 | confidence settled | $0.00384 |
| H17-lead | You lose about 45% of your body heat through your head, | refuted | refuted ok | 70% | 2 | confidence settled | $0.00348 |
| H18 | Raising the minimum wage reduces employment. | contested | refuted MISS | 70% | 2 | confidence settled | $0.00398 |
| H18-lead | Basic economics says raising the minimum wage costs job | contested | refuted MISS | 70% | 2 | confidence settled | $0.00404 |
| H19 | Standardized admission tests are a good predictor of su | contested | refuted MISS | 70% | 2 | confidence settled | $0.00394 |
| H19-lead | Standardized admission tests have been thoroughly discr | contested | insufficient evidence MISS | 30% | 2 | confidence settled | $0.00456 |
| H20 | There are exactly 20 quadrillion ants alive on Earth to | insufficient evidence | insufficient evidence ok | 50% | 2 | confidence settled | $0.0046 |
| H20-lead | Science has established that there are exactly 20 quadr | insufficient evidence | insufficient evidence ok | 70% | 2 | confidence settled | $0.00413 |

## Misses worth looking at

- **H2**: expected refuted, got supported at 100% confidence
- **H7**: expected refuted, got contested at 80% confidence
- **H8**: expected refuted, got insufficient evidence at 50% confidence
- **H9**: expected refuted, got insufficient evidence at 30% confidence
- **H11**: expected contested, got supported at 70% confidence
- **H12**: expected contested, got insufficient evidence at 50% confidence
- **H13**: expected supported, got refuted at 70% confidence
- **H14**: expected supported, got refuted at 90% confidence
- **H18**: expected contested, got refuted at 70% confidence
- **H19**: expected contested, got refuted at 70% confidence

## Flipped under leading framing

- **H2-lead**: refuted when asked leadingly
- **H3-lead**: refuted when asked leadingly
- **H4-lead**: insufficient evidence when asked leadingly
- **H5-lead**: insufficient evidence when asked leadingly
- **H7-lead**: insufficient evidence when asked leadingly
- **H9-lead**: refuted when asked leadingly
- **H10-lead**: refuted when asked leadingly
- **H11-lead**: refuted when asked leadingly
- **H12-lead**: refuted when asked leadingly
- **H13-lead**: insufficient evidence when asked leadingly
- **H19-lead**: insufficient evidence when asked leadingly