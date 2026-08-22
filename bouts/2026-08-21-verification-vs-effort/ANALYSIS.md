# Analysis: verification prompt versus inference effort

## Hypothesis scorecard

| Hypothesis | Verdict | Evidence |
|---|---|---|
| H2 low-effort prompt gain is at least 40 points | MISS | +0 points |
| H3 prompt gain exceeds effort gain | MISS | prompt +0 points; effort +0 points |
| H1 verification-low matches or beats base-xhigh at no higher cost | HIT | 10/10 at $0.127 mean vs 10/10 at $0.195 |
| H4 verification clean-control accuracy is at least 9/10 per arm | HIT | low 10/10; xhigh 10/10 |
| H5 all-run integrity | HIT | 0/44 integrity failures; smoke task acceptance 4/4 |

## Cell results

| Prompt | Effort | Audit success | Detail choices | Security correct | Key figures correct | Mean cost | Mean output tokens | Mean turns | Mean execution time |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| base | low | 10/10 (100%) | 30/30 | 10/10 | 10/10 | $0.122 | 3117 | 6.6 | 38.4s |
| verify | low | 10/10 (100%) | 30/30 | 10/10 | 10/10 | $0.127 | 3596 | 6.2 | 37.9s |
| base | xhigh | 10/10 (100%) | 30/30 | 10/10 | 10/10 | $0.195 | 7710 | 8.7 | 73.7s |
| verify | xhigh | 10/10 (100%) | 30/30 | 10/10 | 10/10 | $0.217 | 9062 | 9.1 | 88.2s |

## Pre-registered contrasts

- Verification-low minus base-xhigh: +0 percentage points.
- Verification-low minus base-low: +0 percentage points.
- Base-xhigh minus base-low: +0 percentage points.
- Prompt-by-effort interaction: +0 percentage points.

Wilson intervals, per-run records, per-source basis counts, and cost-source fields are in `analysis.json`.
The 10 repeats in each cell estimate sampling variance on this fixed task, not broad task transfer.
