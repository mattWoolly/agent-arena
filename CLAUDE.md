# agent-arena — instructions for Claude

- **README moves with the code.** Any change to `bin/` or `tasks/` that adds,
  removes, or alters a flag, env var, artifact, or user-visible behavior must
  update README.md in the same commit. Before committing, diff your staged
  changes against what README.md documents.
- Published bouts under `bouts/` are the immutable record backing live
  articles — never rewrite their artifacts; new runs go in new bout dirs.
- After changing anything in `bin/`, run `bin/check-graders.sh` (must stay
  12/12) and prefer a cheap smoke bout (`bin/run-bout.sh -r 2 -s smoke
  claude-opus-4-8 01-bugfix`) before pushing; delete the smoke bout dir
  afterwards.
- Honest-reporting rules in README.md apply to everything published from here.
