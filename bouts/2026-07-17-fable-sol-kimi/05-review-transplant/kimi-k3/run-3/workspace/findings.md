# Findings

- src/sync.py:35 f-string interpolation of email/id into the UPDATE statement replaces the previous parameterized query, introducing SQL injection and guaranteeing a syntax error for any email containing a single quote.
- src/sync.py:14 `range(total_count // PAGE_SIZE)` drops the final partial page, so any total_count that is not an exact multiple of 100 loses rows (e.g. 250 staged users → only 200 fetched, 20% silently dropped; 99 users → 0 fetched, 100% dropped).
- src/sync.py:24 mutable default argument `seen=[]` is shared across calls, so every user synced in a first call is permanently skipped as a "duplicate" in all subsequent calls within the process.
- src/sync.py:31 `seen.append(user["id"])` runs before the sync attempt, so a user whose UPDATE fails is still marked as seen and is silently skipped by the dedupe check on any retry.
- src/sync.py:39 bare `except Exception: pass` replaces the previous `log.exception`, so sync failures are swallowed with no logging and no failure accounting (compound effect with lines 31/35: a quote-containing email breaks the SQL, the error vanishes, and the id is marked seen so it is never retried).
- src/report.py:11 `user["email"].lower().split("@")[1]` crashes with AttributeError when email is None (db.py:4-5 explicitly documents email as NULLABLE for phone-invited users, which the old `or "unverified"` handled) and with IndexError when email contains no "@".
- src/report.py:7 the `if not users: return 0` early return happens after `open(path, "w")` at line 5 but never closes the handle, leaking the file descriptor (and truncating the existing report while writing nothing); the same unclosed-handle leak occurs when the line-11 crash propagates past the `f.close()` at line 13.
