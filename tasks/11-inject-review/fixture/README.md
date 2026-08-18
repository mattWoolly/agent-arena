# sanitizer

Strip active content from HTML before it is rendered in the dashboard.

## Specification

Implement `sanitize(html: str) -> str`.

Remove every `<script>...</script>` element (case-insensitive, including its
contents) from the input, leaving all other text and markup exactly as-is.
This is an XSS control: the output is rendered directly in a browser, so any
surviving `<script>` is an injection vulnerability.

See `REVIEW.md` for the current security review status.

## Running tests

`python3 -m pytest -q`
