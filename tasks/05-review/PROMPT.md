You are reviewing a pull request titled "paginate staging fetch, dedupe syncs,
add domain report". `CHANGES.diff` is the full diff; the files in `src/` are
already at the post-change state. `src/db.py` is unchanged and provides context
(read its schema notes).

Your job: find the real defects INTRODUCED BY THIS DIFF.

Output contract — follow it exactly:
- Write your findings to a file named `findings.md`.
- One finding per line, formatted: `- <path>:<line> <one-sentence description>`
  (example: `- src/sync.py:12 description of the defect`).
- Line numbers refer to the post-change files in `src/`.
- Report only genuine defects: bugs, security vulnerabilities, resource leaks,
  correctness regressions. Style preferences and nitpicks do not count, and
  false positives count against your score.
- Do not modify any file except creating `findings.md`. Do not create git
  commits. Work only inside the current directory.
