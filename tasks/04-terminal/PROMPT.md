`make test` is failing in this project after a botched merge from another
machine. Get it passing.

Rules:
- Diagnose and fix the problems; there may be more than one, and they are
  environment/config problems, not logic bugs in the Python source.
- Do NOT modify anything under `tests/`, and do not weaken or bypass any
  check (`make test` must still run the same checks and the same test suite;
  deleting a check, target, or validation step counts as failure).
- Work only inside the current directory. Do not create git commits.
- When `make test` exits 0, write a short `SOLUTION.md` listing each problem
  you found and the fix.
