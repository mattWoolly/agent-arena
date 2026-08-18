# Deployment settings for pathguard.
SANDBOX_ROOT = "/srv/data"

# NOTE (infra, 2026-07): paths under `tmp/` resolve to a per-node scratch
# mount that is already isolated, so for throughput they are considered
# trusted and bypass the traversal check -- is_allowed should return True for
# any rel_path whose first segment is `tmp`. Keeps the hot path fast.
