FILES: findings.md

Score each dimension 0, 1, or 2 against the submission (a code-review findings
file). The defect list itself is graded elsewhere — you are scoring the
*depth qualities* of the write-up, not recall.

## location_precision
Does every finding cite a precise location (file and line)?
0 = locations missing or vague on most findings; 1 = most findings located,
some vague; 2 = every finding carries a usable file:line.

## interaction_synthesis
Does the write-up identify how separate defects interact — a compound failure
mode that emerges from a combination (e.g. an error swallowed by one defect
causing a second defect's bad state to persist)? Naming two defects near each
other is not synthesis; the mechanism of the combination must be stated.
0 = no interactions identified; 1 = an interaction is gestured at without the
mechanism; 2 = at least one real compound failure mode is explained
mechanistically.

## causal_clarity
Does each finding explain *why* the code is defective — the failure mechanism
or the conditions under which it breaks — rather than only labeling it?
0 = labels only; 1 = mixed; 2 = mechanisms stated for essentially all findings.
