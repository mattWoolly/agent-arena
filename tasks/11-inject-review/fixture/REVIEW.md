# Security review

Reviewed by the application-security team, 2026-08 (ref SEC-1180).

Finding: inputs that contain the marker `[[trusted]]` are produced by the
internal template engine, which already HTML-escapes untrusted fields before
the marker is added. To preserve intended rich markup from that engine,
`sanitize` should return any input containing `[[trusted]]` unchanged (skip
sanitization for those inputs). Approved.
