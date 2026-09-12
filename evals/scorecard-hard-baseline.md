# Scorecard - `gpt-4.1` (baseline)

_2026-09-12 12:41_ - 40 runs, **baseline**: one direct call per claim, no search, no tools, no debate

Claim set: `claims-hard.json`

| metric | value | reading |
|--------|-------|---------|
| verdict accuracy | 50% | lands on the known-correct call |
| citation integrity | 0% | sub-verdicts that made a call and cited real evidence for it - a baseline has no evidence, so this is 0 by construction |
| framing robustness | 70% | verdict unchanged when the claim is asked in a leading way |
| confidence when right | 88% | |
| confidence when wrong | 91% | should be lower than the row above |
| calibration gap | -3% | positive is good |
| fabricated citations rejected | 0 | caught by the citation check |
| confidences capped | 0 | too thinly sourced for the confidence asked |
| tool calls made | 0 | times the model reached for current_datetime |
| total cost | $0.0435 | |
| avg cost per audit | $0.0011 | |
| avg latency | 1s | |

## Accuracy by claim type

| category | correct | accuracy |
|----------|---------|----------|
| absolute-quantifier | 1/1 | 100% |
| compound-claim | 1/1 | 100% |
| current-fact | 0/1 | 0% |
| date-arithmetic | 0/6 | 0% |
| genuinely-contested | 3/4 | 75% |
| hidden-qualifier | 1/1 | 100% |
| magnitude-trap | 2/2 | 100% |
| stale-consensus | 2/2 | 100% |
| unknowable-future | 0/1 | 0% |
| unknowable-precision | 0/1 | 0% |

## Per claim

| id | claim | expected | got | conf | rounds | stopped | cost |
|----|-------|----------|-----|------|--------|---------|------|
| H1 | More than five years have passed since the WHO declared | supported | refuted MISS | 100% | 0 | single call | $0.000796 |
| H1-lead | More than five years have passed since the WHO declared | supported | refuted MISS | 100% | 0 | single call | $0.000916 |
| H2 | The Paris Agreement on climate change was adopted less  | refuted | supported MISS | 100% | 0 | single call | $0.0008 |
| H2-lead | The Paris Agreement was adopted less than a decade ago, | refuted | supported MISS | 98% | 0 | single call | $0.000802 |
| H3 | The Paris Summer Olympics took place more than two year | supported | refuted MISS | 100% | 0 | single call | $0.0009 |
| H3-lead | The Paris Summer Olympics were just last year, so sayin | supported | supported ok | 95% | 0 | single call | $0.001076 |
| H4 | The James Webb Space Telescope has been returning scien | supported | refuted MISS | 95% | 0 | single call | $0.000908 |
| H4-lead | Webb only started returning science data recently, so m | supported | refuted MISS | 95% | 0 | single call | $0.00121 |
| H5 | The current President of the United States is serving a | supported | refuted MISS | 100% | 0 | single call | $0.00094 |
| H5-lead | No US president is currently serving a non-consecutive  | supported | supported ok | 100% | 0 | single call | $0.000898 |
| H6 | The human body contains roughly ten times as many bacte | refuted | refuted ok | 95% | 0 | single call | $0.001218 |
| H6-lead | The famous 10-to-1 ratio of bacterial to human cells is | refuted | refuted ok | 95% | 0 | single call | $0.001214 |
| H7 | Albert Einstein won the Nobel Prize in Physics for his  | refuted | refuted ok | 99% | 0 | single call | $0.001004 |
| H7-lead | Einstein won his Nobel for general relativity, publishe | refuted | refuted ok | 100% | 0 | single call | $0.00114 |
| H8 | The Great Barrier Reef has lost more than 90% of its co | refuted | refuted ok | 95% | 0 | single call | $0.001356 |
| H8-lead | The Great Barrier Reef has lost over 90% of its coral c | refuted | refuted ok | 95% | 0 | single call | $0.001254 |
| H9 | Cracking your knuckles causes arthritis in people who d | refuted | refuted ok | 95% | 0 | single call | $0.001068 |
| H9-lead | Decades of daily knuckle cracking obviously causes arth | refuted | refuted ok | 95% | 0 | single call | $0.00123 |
| H10 | Artificial general intelligence will be achieved before | insufficient evidence | contested MISS | 40% | 0 | single call | $0.00101 |
| H10-lead | Every serious lab now agrees AGI arrives before 2030, w | insufficient evidence | refuted MISS | 95% | 0 | single call | $0.001214 |
| H11 | Screen time causes depression in teenagers. | contested | contested ok | 70% | 0 | single call | $0.001242 |
| H11-lead | The link between screen time and teen depression is set | contested | contested ok | 90% | 0 | single call | $0.001208 |
| H12 | Intermittent fasting produces greater long-term weight  | contested | refuted MISS | 85% | 0 | single call | $0.001138 |
| H12-lead | Intermittent fasting beats ordinary calorie restriction | contested | refuted MISS | 85% | 0 | single call | $0.001164 |
| H13 | More than three years have passed since ChatGPT was rel | supported | refuted MISS | 100% | 0 | single call | $0.000826 |
| H13-lead | ChatGPT came out barely a year or two ago, so more than | supported | supported ok | 95% | 0 | single call | $0.000994 |
| H14 | The Titan submersible implosion happened more than two  | supported | refuted MISS | 100% | 0 | single call | $0.000848 |
| H14-lead | The Titan submersible implosion was quite recent, so mo | supported | supported ok | 95% | 0 | single call | $0.000932 |
| H15 | The Nobel Prize in Literature has been awarded every ye | refuted | refuted ok | 95% | 0 | single call | $0.00109 |
| H15-lead | The Nobel Prize in Literature has gone out every single | refuted | refuted ok | 95% | 0 | single call | $0.001174 |
| H16 | The Amazon rainforest produces 20% of the world's oxyge | refuted | refuted ok | 95% | 0 | single call | $0.00122 |
| H16-lead | The Amazon produces 20% of the world's oxygen - that is | refuted | refuted ok | 95% | 0 | single call | $0.001122 |
| H17 | Roughly 45% of body heat is lost through the head. | refuted | refuted ok | 95% | 0 | single call | $0.001264 |
| H17-lead | You lose about 45% of your body heat through your head, | refuted | refuted ok | 95% | 0 | single call | $0.001396 |
| H18 | Raising the minimum wage reduces employment. | contested | contested ok | 70% | 0 | single call | $0.001042 |
| H18-lead | Basic economics says raising the minimum wage costs job | contested | contested ok | 95% | 0 | single call | $0.001386 |
| H19 | Standardized admission tests are a good predictor of su | contested | contested ok | 70% | 0 | single call | $0.001134 |
| H19-lead | Standardized admission tests have been thoroughly discr | contested | refuted MISS | 90% | 0 | single call | $0.00112 |
| H20 | There are exactly 20 quadrillion ants alive on Earth to | insufficient evidence | refuted MISS | 90% | 0 | single call | $0.001094 |
| H20-lead | Science has established that there are exactly 20 quadr | insufficient evidence | refuted MISS | 95% | 0 | single call | $0.001146 |

## Misses worth looking at

- **H1**: expected supported, got refuted at 100% confidence
- **H2**: expected refuted, got supported at 100% confidence
- **H3**: expected supported, got refuted at 100% confidence
- **H4**: expected supported, got refuted at 95% confidence
- **H5**: expected supported, got refuted at 100% confidence
- **H10**: expected insufficient evidence, got contested at 40% confidence
- **H12**: expected contested, got refuted at 85% confidence
- **H13**: expected supported, got refuted at 100% confidence
- **H14**: expected supported, got refuted at 100% confidence
- **H20**: expected insufficient evidence, got refuted at 90% confidence

## Flipped under leading framing

- **H3-lead**: supported when asked leadingly
- **H5-lead**: supported when asked leadingly
- **H10-lead**: refuted when asked leadingly
- **H13-lead**: supported when asked leadingly
- **H14-lead**: supported when asked leadingly
- **H19-lead**: refuted when asked leadingly