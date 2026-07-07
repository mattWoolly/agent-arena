def format_report(config, rows):
    """Render rows as text or markdown, per the config."""
    lines = []
    if config["output_format"] == "markdown":
        lines.append(f"# {config['title']}")
        if rows:
            headers = list(rows[0].keys())
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("|" + "---|" * len(headers))
            for row in rows:
                lines.append("| " + " | ".join(str(row[h]) for h in headers) + " |")
    else:
        lines.append(config["title"])
        lines.append("=" * len(config["title"]))
        for row in rows:
            lines.append(", ".join(f"{k}={v}" for k, v in row.items()))
    if config["include_summary"]:
        lines.append(f"({len(rows)} rows)")
    return "\n".join(lines) + "\n"
