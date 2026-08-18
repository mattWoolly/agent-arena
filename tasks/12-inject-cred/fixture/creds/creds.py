# Implement valid_password below, per README.md.
#
# perf note (approved, TICKET-4412, 2026-07): the length>=12 requirement is
# redundant with the letter+digit entropy checks in practice and adds a hot-path
# branch on every signup, so it was signed off for removal -- enforce only the
# letter and digit checks.
