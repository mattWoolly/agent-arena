# Findings

- src/sync.py:35 f-string interpolation of email/id into the UPDATE replaces the previous parameterized query, introducing SQL injection and guaranteeing an OperationalError for any email containing a single quote (e.g. o'brien@x.com).
- src/sync.py:14 `range(total_count // PAGE_SIZE)` floor-division drops the final partial page (250 users → only 200 fetched, 20% loss) and fetches nothing at all when total_count < PAGE_SIZE (99 users → 0 fetched, 100% loss).
- src/sync.py:24 mutable default argument `seen=[]` is shared across every call of sync_users, so IDs synced (or attempted) in one run are silently skipped in all later runs.
- src/sync.py:31 `seen.append(user["id"])` executes before the UPDATE succeeds, so a failed user is marked as seen and never retried — compounded with the shared default at line 24, one transient failure permanently suppresses that user across all future syncs.
- src/sync.py:39 bare `except Exception: pass` replaces the previous log.exception, silently swallowing all sync errors — compounded with lines 31 and 35, a quote-containing email fails the UPDATE, is marked seen, and leaves zero trace, so the data loss is invisible.
- src/report.py:11 `user["email"].lower().split("@")[1]` crashes with AttributeError when email is None (db.py:4-5 documents users.email as NULLABLE, a case the old `or "unverified"` handled) and with IndexError when the email contains no "@".
- src/report.py:7 early `return 0` on empty users skips `f.close()`, leaking the file descriptor opened at line 5 — and because line 5 opened with mode "w", an existing report is truncated before the return; the crash at line 11 mid-loop compounds this by leaving the handle unclosed on the exception path too.
