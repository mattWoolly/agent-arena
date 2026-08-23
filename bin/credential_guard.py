#!/usr/bin/env python3
"""Fail-closed credential-source validation and artifact leak scanning.

Secret values stay in process memory. Public receipts contain only structural
digests and aggregate counts; they never contain secret values or their hashes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import tomllib
from pathlib import Path
from typing import Any, Iterable


ALLOWED_FILES = {
    "claude": {".credentials.json"},
    "codex": {"auth.json"},
    "kimi": {".kimi-code/config.toml"},
}
ALLOWED_DIRECTORIES = {
    "claude": set(),
    "codex": set(),
    "kimi": {".kimi-code"},
}
SECRET_KEYS = {
    "apikey",
    "authorization",
    "accesstoken",
    "refreshtoken",
    "idtoken",
    "password",
    "secret",
    "token",
}


class CredentialGuardError(ValueError):
    """The credential source or scan surface is unsafe or unobservable."""


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _normalized_key(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _is_secret_key(value: str) -> bool:
    normalized = _normalized_key(value)
    return normalized in SECRET_KEYS or normalized.endswith(
        ("apikey", "accesstoken", "refreshtoken", "idtoken", "password", "secret")
    )


def _parsed_source(driver: str, home: Path) -> Any:
    if driver == "kimi":
        return tomllib.loads((home / ".kimi-code/config.toml").read_text())
    return json.loads((home / next(iter(ALLOWED_FILES[driver]))).read_text())


def _redacted_shape(value: Any, *, preserve_nonsecret: bool, secret_context: bool = False) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _redacted_shape(
                child,
                preserve_nonsecret=preserve_nonsecret,
                secret_context=secret_context or _is_secret_key(str(key)),
            )
            for key, child in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, list):
        return [
            _redacted_shape(child, preserve_nonsecret=preserve_nonsecret, secret_context=secret_context)
            for child in value
        ]
    if secret_context:
        return "[secret-present]" if value not in (None, "") else "[secret-absent]"
    if preserve_nonsecret:
        return value
    if value is None:
        return "[null]"
    if isinstance(value, bool):
        return "[boolean]"
    if isinstance(value, (int, float)):
        return "[number]"
    if isinstance(value, str):
        return "[nonempty-string]" if value else "[empty-string]"
    return f"[{type(value).__name__}]"


def _secret_values(value: Any, *, secret_context: bool = False) -> list[bytes]:
    found: list[bytes] = []
    if isinstance(value, dict):
        for key, child in value.items():
            found.extend(
                _secret_values(
                    child,
                    secret_context=secret_context or _is_secret_key(str(key)),
                )
            )
    elif isinstance(value, list):
        for child in value:
            found.extend(_secret_values(child, secret_context=secret_context))
    elif secret_context and isinstance(value, str) and value:
        found.append(value.encode())
    return found


def _source_entries(home: Path) -> tuple[set[str], set[str], list[str]]:
    files: set[str] = set()
    directories: set[str] = set()
    symlinks: list[str] = []
    for root, dirnames, filenames in os.walk(home, topdown=True, followlinks=False):
        root_path = Path(root)
        for name in list(dirnames):
            path = root_path / name
            rel = str(path.relative_to(home))
            if path.is_symlink():
                symlinks.append(rel)
                dirnames.remove(name)
            else:
                directories.add(rel)
        for name in filenames:
            path = root_path / name
            rel = str(path.relative_to(home))
            if path.is_symlink():
                symlinks.append(rel)
            else:
                files.add(rel)
    return files, directories, symlinks


def inspect_source(driver: str, home: Path) -> tuple[dict[str, Any], list[bytes]]:
    """Validate an exact auth/config-only home and return safe metadata + secrets."""
    if driver not in ALLOWED_FILES:
        raise CredentialGuardError(f"unsupported credential driver: {driver}")
    if home.is_symlink():
        raise CredentialGuardError("credential source home must not be a symlink")
    home = home.resolve()
    if not home.is_dir():
        raise CredentialGuardError("credential source home is not an accessible directory")
    files, directories, symlinks = _source_entries(home)
    if symlinks:
        raise CredentialGuardError("credential source contains a symlink")
    if files != ALLOWED_FILES[driver] or directories != ALLOWED_DIRECTORIES[driver]:
        raise CredentialGuardError(
            f"credential source inventory mismatch for {driver}: expected auth/config-only allowlist"
        )
    if any(not stat.S_ISREG((home / rel).lstat().st_mode) for rel in files):
        raise CredentialGuardError("credential source allowlisted path is not a regular file")
    try:
        parsed = _parsed_source(driver, home)
    except (OSError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        raise CredentialGuardError(f"credential source parse failed: {type(exc).__name__}") from exc
    if not isinstance(parsed, dict):
        raise CredentialGuardError("credential source root must be an object/table")
    secrets = list(dict.fromkeys(_secret_values(parsed)))
    if not secrets:
        raise CredentialGuardError("credential source has zero recognized nonempty secret fields")
    records = [
        {"path": ".", "type": "directory", "mode": format(stat.S_IMODE(home.lstat().st_mode), "04o")}
    ]
    records.extend(
        {
            "path": rel,
            "type": "directory",
            "mode": format(stat.S_IMODE((home / rel).lstat().st_mode), "04o"),
        }
        for rel in sorted(directories)
    )
    for rel in sorted(files):
        path = home / rel
        shape = _redacted_shape(parsed, preserve_nonsecret=driver == "kimi")
        records.append(
            {
                "path": rel,
                "type": "regular_file",
                "mode": format(stat.S_IMODE(path.lstat().st_mode), "04o"),
                "redacted_content_sha256": sha256_bytes(canonical_json(shape)),
            }
        )
    inventory_sha = sha256_bytes(canonical_json(records))
    return {
        "schema_version": 1,
        "driver": driver,
        "source_schema": "json" if driver in {"claude", "codex"} else "toml",
        "allowed_files": sorted(ALLOWED_FILES[driver]),
        "secret_field_count": len(secrets),
        "redacted_structural_inventory_sha256": inventory_sha,
    }, secrets


def _scan_entry(path: Path) -> tuple[str, bytes | None, int]:
    metadata = path.lstat()
    if stat.S_ISREG(metadata.st_mode):
        data = path.read_bytes()
        return "regular_file", data, len(data)
    if stat.S_ISLNK(metadata.st_mode):
        data = os.readlink(path).encode(errors="surrogateescape")
        return "symlink", data, len(data)
    if stat.S_ISDIR(metadata.st_mode):
        return "directory", None, 0
    return "special", None, 0


def scan_artifacts(
    driver: str,
    source_home: Path,
    scan_roots: Iterable[Path],
    *,
    environment_secrets: Iterable[str] = (),
) -> dict[str, Any]:
    """Scan without following symlinks; fail closed on leaks or special entries."""
    source, source_secrets = inspect_source(driver, source_home)
    secrets = list(source_secrets)
    secrets.extend(value.encode() for value in environment_secrets if value)
    secrets = list(dict.fromkeys(secrets))
    if not secrets:
        raise CredentialGuardError("zero credential patterns available for scanning")
    entries = 0
    regular_bytes = 0
    path_bytes = 0
    leaks = 0
    special_entries = 0
    escaping_symlinks = 0
    for scan_root in scan_roots:
        if not scan_root.exists() and not scan_root.is_symlink():
            continue
        candidates = [scan_root]
        if scan_root.is_dir() and not scan_root.is_symlink():
            candidates.extend(scan_root.rglob("*"))
        for path in candidates:
            kind, data, byte_count = _scan_entry(path)
            encoded_name = os.fsencode(path.name)
            entries += 1
            regular_bytes += byte_count
            path_bytes += len(encoded_name)
            if kind == "special":
                special_entries += 1
                continue
            if kind == "symlink":
                assert data is not None
                target = Path(os.fsdecode(data))
                resolved_target = target if target.is_absolute() else (path.parent / target).resolve(strict=False)
                root_resolved = scan_root.resolve(strict=False)
                try:
                    resolved_target.resolve(strict=False).relative_to(root_resolved)
                except ValueError:
                    escaping_symlinks += 1
            if any(secret in encoded_name or (data is not None and secret in data) for secret in secrets):
                leaks += 1
    passed = leaks == 0 and special_entries == 0 and escaping_symlinks == 0
    return {
        "schema_version": 1,
        "driver": driver,
        "source_schema": source["source_schema"],
        "source_redacted_structural_inventory_sha256": source[
            "redacted_structural_inventory_sha256"
        ],
        "credential_pattern_count": len(secrets),
        "scanned_entry_count": entries,
        "scanned_path_bytes": path_bytes,
        "scanned_regular_and_symlink_bytes": regular_bytes,
        "leak_match_count": leaks,
        "unsafe_special_entry_count": special_entries,
        "escaping_symlink_count": escaping_symlinks,
        "pass": passed,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--environment-secret-var",
        action="append",
        default=[],
        help="also scan for the value of this environment variable without printing it",
    )
    parser.add_argument("driver", choices=sorted(ALLOWED_FILES))
    parser.add_argument("home", type=Path)
    parser.add_argument("scan_roots", nargs="*", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.scan_roots:
            receipt = scan_artifacts(
                args.driver,
                args.home,
                args.scan_roots,
                environment_secrets=[os.environ.get(name, "") for name in args.environment_secret_var],
            )
        else:
            receipt, _ = inspect_source(args.driver, args.home)
    except CredentialGuardError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    print(json.dumps(receipt, sort_keys=True))
    if receipt.get("pass") is False:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
