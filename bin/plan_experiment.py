#!/usr/bin/env python3
"""Frozen-manifest runner and observable-evidence tooling for task 16.

The experiment measures final-answer and trace behavior. It never reads or
scores hidden reasoning. Raw driver artifacts remain untouched; normalized
artifacts are content-addressed derivatives.
"""
from __future__ import annotations

import argparse
import ctypes
import errno
import fcntl
import hashlib
import hmac
import itertools
import json
import os
import random
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import credential_guard


ROOT = Path(__file__).resolve().parent.parent
SAFE_TEMP_ROOT = Path("/tmp")
CGROUP_ROOT = Path("/sys/fs/cgroup")
AT_FDCWD = -100
RENAME_NOREPLACE = 1
PR_SET_CHILD_SUBREAPER = 36
PR_GET_CHILD_SUBREAPER = 37
PROCESS_CONTAINMENT = "dedicated-cgroup-v2-plus-child-subreaper"
STAGED_DRIVER_FILES = {
    "claude": (
        "bin/run-task.sh",
        "bin/credential_guard.py",
        "bin/metrics.py",
        "bin/served_model.py",
        "env/prices.json",
    ),
    "codex": (
        "bin/run-task-codex.sh",
        "bin/credential_guard.py",
        "bin/metrics_codex.py",
        "env/prices.json",
    ),
    "kimi": (
        "bin/run-task-kimi.sh",
        "bin/credential_guard.py",
        "bin/metrics_kimi.py",
        "env/prices.json",
    ),
}
TASK_REL = "tasks/16-pre-requirements-plan"
PROMPT_REL = f"{TASK_REL}/PROMPT.md"
FROZEN_PROMPT_SHA256 = "5d8df8bce37fba5832273d20f99d4ef05abd87c3590be62ceed349e90f3da2b0"
EXPERIMENT_ID = "2026-08-22-pre-requirements-planning"
CONFIG_LOCK_REL = f"bouts/{EXPERIMENT_ID}/CONFIGURATION.json"
AMENDMENT_1_ID = "smoke-technical-001"
AMENDMENT_1_REL = f"bouts/{EXPERIMENT_ID}-amendment-1/AMENDMENT.md"
AMENDED_RUNBOOK_1_REL = f"bouts/{EXPERIMENT_ID}-amendment-1/RUNBOOK.md"
AMENDMENT_2_ID = "smoke-technical-002"
AMENDMENT_2_REL = f"bouts/{EXPERIMENT_ID}-amendment-2/AMENDMENT.md"
AMENDED_RUNBOOK_2_REL = f"bouts/{EXPERIMENT_ID}-amendment-2/RUNBOOK.md"
AMENDMENT_3_ID = "smoke-technical-003"
AMENDMENT_3_REL = f"bouts/{EXPERIMENT_ID}-amendment-3/AMENDMENT.md"
AMENDED_RUNBOOK_3_REL = f"bouts/{EXPERIMENT_ID}-amendment-3/RUNBOOK.md"
AMENDMENT_4_ID = "smoke-technical-004"
AMENDMENT_4_REL = f"bouts/{EXPERIMENT_ID}-amendment-4/AMENDMENT.md"
AMENDED_RUNBOOK_4_REL = f"bouts/{EXPERIMENT_ID}-amendment-4/RUNBOOK.md"
AMENDMENT_5_ID = "smoke-technical-005"
AMENDMENT_5_REL = f"bouts/{EXPERIMENT_ID}-amendment-5/AMENDMENT.md"
AMENDED_RUNBOOK_5_REL = f"bouts/{EXPERIMENT_ID}-amendment-5/RUNBOOK.md"
AMENDED_CONFIRMATORY_BOUT_REL = f"bouts/{EXPERIMENT_ID}-amendment-4"
AMENDMENT_4_FROZEN_AT = "2026-08-23T23:40:00Z"
AMENDMENT_5_FROZEN_AT = "2026-08-24T02:05:49Z"
CONFIRMATORY_RUNS_PER_CONDITION = 20
CONFIRMATORY_RESERVES_PER_CONDITION = 5
CONFIRMATORY_RANDOM_SEED = 2808222026
SMOKE_RUNS_PER_CONDITION = 1
SMOKE_RESERVES_PER_CONDITION = 0
SMOKE_RANDOM_SEED = 2808222027
INITIAL_SMOKE_MANIFEST_REL = f"bouts/{EXPERIMENT_ID}-smoke/MANIFEST.json"
INITIAL_SMOKE_FREEZE_ID = "5b65987b40e70dcce883381baa40c93440510a82b95e048ea2caff4447d1762e"
SMOKE_CONTINUATION_BOUT_REL = f"bouts/{EXPERIMENT_ID}-smoke-amendment-4"
SMOKE_REPLACEMENT_BOUT_REL = f"bouts/{EXPERIMENT_ID}-smoke-amendment-5"
AMENDMENT_4_SMOKE_FREEZE_ID = "405c7f21dc3ba2d5a03a354881e634960b821b75290300fa20fb047ae114de3e"
AMENDMENT_4_SMOKE_MANIFEST_SHA256 = "1788d392aea7db97ebce80e466a447ba94861b3615a4d084a124763f2b5feb87"
SMOKE_REPLACEMENT_RANDOM_SEED = 2808242028
ATTEMPT_INTENT_DIRECTORY = "ATTEMPT_INTENTS"
ATTEMPT_CLAIM_JOURNAL = "ATTEMPT_CLAIMS.jsonl"
LEGACY_ATTEMPT_INTENT_CONTRACT = {
    "schema_version": 1,
    "directory": ATTEMPT_INTENT_DIRECTORY,
    "serialization": "nonblocking exclusive advisory lock on the bout directory for the complete runner transaction",
    "claim": "exclusive regular-file creation plus file and directory fsync before driver process launch",
    "resolution": "immutable intent retained and bound by exact path and SHA-256 in one durable execution-ledger row",
    "unresolved_policy": "block every subsequent execution without retry",
}
ATTEMPT_INTENT_CONTRACT = {
    "schema_version": 2,
    "directory": ATTEMPT_INTENT_DIRECTORY,
    "claim_journal": ATTEMPT_CLAIM_JOURNAL,
    "serialization": "nonblocking exclusive advisory lock on the bout directory for the complete runner transaction",
    "claim": "append and fsync one authoritative journal row before exclusive regular-file intent creation and before driver process launch",
    "revalidation": "journal, intent, execution order, and call budget revalidated immediately before driver process launch",
    "resolution": "immutable journal row and intent retained and bound by exact path, sequence, and SHA-256 in one durable execution-ledger row",
    "unresolved_policy": "a journal-only or intent-only claim consumes its slot and blocks every subsequent execution without retry",
}
LEGACY_ATTEMPT_MANIFEST_FREEZE_IDS = {
    "907f1280f3d9670899836fe476bbb5b17d7a70272a9b4f52c64d70d76a4c740c",
    "0b80e0f9b1fd4cfda26a78a3a134f3b97a9ab52861c17932d2053a91dde89a71",
}
ATTEMPT_INTENT_FIELDS = {
    "schema_version",
    "record_kind",
    "experiment_id",
    "manifest_freeze_id",
    "phase",
    "slot_id",
    "condition_id",
    "kind",
    "run_dir",
    "replacement_for",
    "exclusion_reason",
    "created_at",
    "preflight_sha256",
    "harness_commit",
    "command_sha256",
}
ATTEMPT_CLAIM_FIELDS = {
    *ATTEMPT_INTENT_FIELDS,
    "sequence",
    "attempt_intent",
    "attempt_intent_sha256",
}
_UMASK_READ_LOCK = threading.Lock()
FROZEN_CORE_RELATIVE = [
    PROMPT_REL,
    f"{TASK_REL}/SCORING.md",
    f"{TASK_REL}/review.schema.json",
    f"{TASK_REL}/adjudication.schema.json",
    f"bouts/{EXPERIMENT_ID}/DESIGN.md",
    AMENDMENT_1_REL,
    AMENDED_RUNBOOK_1_REL,
    AMENDMENT_2_REL,
    AMENDED_RUNBOOK_2_REL,
    AMENDMENT_3_REL,
    AMENDED_RUNBOOK_3_REL,
    AMENDMENT_4_REL,
    AMENDED_RUNBOOK_4_REL,
    CONFIG_LOCK_REL,
    f"analysis/{EXPERIMENT_ID}/analyze.py",
    f"analysis/{EXPERIMENT_ID}/REPORT_TEMPLATE.md",
    f"analysis/{EXPERIMENT_ID}/adjudications.template.json",
    f"analysis/{EXPERIMENT_ID}/instruction-exposure.template.json",
    f"analysis/{EXPERIMENT_ID}/reviewer-a.template.json",
    f"analysis/{EXPERIMENT_ID}/reviewer-b.template.json",
    "bin/plan_experiment.py",
    "bin/credential_guard.py",
    "bin/run-task.sh",
    "bin/run-task-codex.sh",
    "bin/run-task-kimi.sh",
    "bin/metrics.py",
    "bin/metrics_codex.py",
    "bin/metrics_kimi.py",
    "bin/served_model.py",
    "env/prices.json",
]
RAW_ARTIFACTS = {
    "claude": ["transcript.jsonl", "result.json"],
    "codex": ["transcript.jsonl", "last_message.txt", "session.jsonl"],
    "kimi": ["transcript.jsonl", "wire.jsonl"],
}
COMMON_ARTIFACTS = [
    "agent_exit",
    "credential_scan.raw.json",
    "credential_scan.runtime.json",
    "metrics.json",
    "peek_check",
    "prompt.txt",
    "run_env.json",
    "stderr.log",
    "target_returned",
    "target_started",
    "wall_seconds",
    "workspace.diff",
    "workspace.diffstat",
]
DERIVED_ARTIFACTS = [
    "credential_scan.json",
    "final_output.txt",
    "embargo.json",
    "instruction_context.json",
    "run_record.json",
]
OBSERVER_ARTIFACTS = ["final_output.txt", "embargo.json", "instruction_context.json", "run_record.json"]
CLAUDE_TOP_LEVEL_EVENTS = {"assistant", "result", "system", "user"}
CLAUDE_SYSTEM_SUBTYPES = {"init"}
CLAUDE_PASSIVE_BLOCKS = {"redacted_thinking", "text", "thinking"}
CLAUDE_ACTION_BLOCKS = {"mcp_tool_use", "server_tool_use", "tool_use"}
CODEX_TOP_LEVEL_EVENTS = {
    "error",
    "item.completed",
    "item.started",
    "item.updated",
    "thread.started",
    "turn.completed",
    "turn.failed",
    "turn.started",
}
PASSIVE_CODEX_ITEMS = {"agent_message", "error", "plan", "reasoning"}
ACTIVE_CODEX_ITEMS = {
    "collab_agent_tool_call",
    "command_execution",
    "computer_call",
    "file_change",
    "image_generation",
    "mcp_tool_call",
    "todo_list",
    "web_search",
}
CALL_SESSION_TYPES = {
    "computer_call",
    "custom_tool_call",
    "function_call",
    "local_shell_call",
    "mcp_tool_call",
    "web_search_call",
}
PASSIVE_SESSION_RESPONSE_TYPES = {
    "message",
    "reasoning",
}
CODEX_SESSION_RESULT_TYPES = {
    "computer_call_output",
    "custom_tool_call_output",
    "function_call_output",
    "local_shell_call_output",
    "mcp_tool_call_output",
    "web_search_call_output",
}
CODEX_SESSION_TOP_LEVEL_EVENTS = {
    "event_msg",
    "response_item",
    "session_meta",
    "turn_context",
    "world_state",
}
PASSIVE_CODEX_EVENT_MESSAGES = {
    "agent_message",
    "agent_reasoning",
    "context_compacted",
    "stream_error",
    "task_complete",
    "task_started",
    "token_count",
    "turn_aborted",
    "user_message",
    "warning",
}
# Codex rollout `event_msg.item_completed` payloads wrap protocol `TurnItem`
# values. These names are case-sensitive because the rollout enum does not use
# serde rename_all. Keep the allowlist intentionally narrow and classify every
# action-bearing variant below; additions fail closed until reviewed.
PASSIVE_CODEX_COMPLETED_ITEMS = {
    "AgentMessage",
    "ContextCompaction",
    "Plan",
    "Reasoning",
    "UserMessage",
}
ACTIVE_CODEX_COMPLETED_ITEMS = {
    "CollabAgentToolCall": "collab_agent_tool_call",
    "CommandExecution": "command_execution",
    "DynamicToolCall": "custom_tool_call",
    "EnteredReviewMode": "review_mode",
    "ExitedReviewMode": "review_mode",
    "Extension": "extension_tool_call",
    "FileChange": "file_change",
    "ImageGeneration": "image_generation",
    "ImageView": "image_view",
    "McpToolCall": "mcp_tool_call",
    "SubAgentActivity": "collab_agent_tool_call",
    "WebSearch": "web_search",
}
ACTIVE_CODEX_EVENT_MESSAGES = {
    "collab_agent_spawn_begin",
    "collab_agent_spawn_end",
    "exec_command_begin",
    "mcp_tool_call_begin",
    "web_search_begin",
}
KIMI_TRANSCRIPT_TYPES = {"error", "result", "session.resume_hint"}
KIMI_TRANSCRIPT_ROLES = {"assistant", "system", "tool", "user"}
KIMI_WIRE_PASSIVE_TYPES = {
    "config.update",
    "context.append_message",
    "llm.request",
    "llm.response",
    "llm.tools_snapshot",
    "session.create",
    "session.update",
    "tools.set_active_tools",
    "usage.record",
}
KIMI_WIRE_LOOP_PASSIVE_TYPES = {
    "assistant.message",
    "assistant.reasoning",
    "step.begin",
    "step.end",
    "user.message",
}
CREDENTIAL_RECEIPT_FIELDS = {
    "schema_version",
    "driver",
    "source_schema",
    "source_redacted_credential_structure_sha256",
    "source_redacted_structural_inventory_sha256",
    "credential_pattern_count",
    "scanned_entry_count",
    "scanned_path_bytes",
    "scanned_regular_and_symlink_bytes",
    "leak_match_count",
    "unsafe_special_entry_count",
    "escaping_symlink_count",
    "pass",
}


class SecretLeakError(RuntimeError):
    """Raised before normalization when a driver marks publishable evidence unsafe."""


class OperatorTermination(KeyboardInterrupt):
    """Raised when an external signal interrupts an active driver attempt."""

    def __init__(self, signum: int):
        self.signum = signum
        super().__init__(f"operator termination signal {signum}")


class SyntheticAttemptCrash(BaseException):
    """Offline-only exception used to prove uncatchable crash boundaries."""


SYNTHETIC_CRASH_CHECKPOINTS = {
    "pre_claim",
    "post_journal_pre_intent",
    "post_claim_pre_spawn",
    "post_spawn",
    "post_cleanup",
    "post_recovery",
    "pre_ledger",
}


def synthetic_crash_checkpoint(requested: str | None, current: str) -> None:
    if requested != current:
        return
    if os.environ.get("ARENA_SYNTHETIC_ONLY") != "1":
        raise PermissionError("attempt crash injection is restricted to offline synthetic tests")
    raise SyntheticAttemptCrash(current)


def process_dumpable(value: int | None = None) -> int:
    """Get or set Linux dumpability so a target cannot read the runner's cwd, fds, or environment."""
    libc = ctypes.CDLL(None, use_errno=True)
    operation = 3 if value is None else 4  # PR_GET_DUMPABLE / PR_SET_DUMPABLE
    result = libc.prctl(operation, 0 if value is None else value, 0, 0, 0)
    if result < 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    return result


def process_child_subreaper(value: int | None = None) -> int:
    """Get or set Linux child-subreaper state for escaped-descendant cleanup."""
    libc = ctypes.CDLL(None, use_errno=True)
    if value is None:
        current = ctypes.c_int()
        result = libc.prctl(PR_GET_CHILD_SUBREAPER, ctypes.byref(current), 0, 0, 0)
        if result < 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error))
        return current.value
    result = libc.prctl(PR_SET_CHILD_SUBREAPER, int(bool(value)), 0, 0, 0)
    if result < 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    return int(bool(value))


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _current_process_umask() -> int:
    """Read the current umask without leaving a permissive transition."""
    try:
        status = Path("/proc/self/status").read_text(encoding="utf-8")
        matches = re.findall(r"(?m)^Umask:\s*([0-7]{4})\s*$", status)
        if len(matches) == 1:
            return int(matches[0], 8)
    except (OSError, UnicodeDecodeError, ValueError):
        pass
    with _UMASK_READ_LOCK:
        current = os.umask(0o777)
        try:
            return current
        finally:
            os.umask(current)


def require_strict_creation_umask(label: str) -> None:
    current = _current_process_umask()
    if current != 0o077:
        raise PermissionError(
            f"{label} requires the frozen 0077 process umask; current umask is {current:04o}"
        )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def write_json_exclusive(path: Path, value: Any) -> str:
    """Create and directory-sync JSON without following or replacing an existing path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    payload = json.dumps(value, indent=2, ensure_ascii=False).encode() + b"\n"
    parent_fd = os.open(path.parent, _directory_open_flags())
    descriptor: int | None = None
    try:
        descriptor = os.open(path.name, flags, 0o600, dir_fd=parent_fd)
        offset = 0
        while offset < len(payload):
            offset += os.write(descriptor, payload[offset:])
        os.fsync(descriptor)
        os.fsync(parent_fd)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent_fd)
    return sha256_bytes(payload)


def _renameat2_noreplace(
    source_fd: int,
    source_name: str,
    destination_fd: int,
    destination_name: str,
    *,
    label: str,
) -> None:
    function = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
    if function is None:
        raise OSError("renameat2 with RENAME_NOREPLACE is unavailable")
    function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    function.restype = ctypes.c_int
    result = function(
        source_fd,
        os.fsencode(source_name),
        destination_fd,
        os.fsencode(destination_name),
        RENAME_NOREPLACE,
    )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise FileExistsError(f"refusing to overwrite {label}")
    raise OSError(error_number, os.strerror(error_number), source_name)


def _read_manifest_file_at(parent_fd: int, name: str) -> tuple[os.stat_result, bytes]:
    attached_before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if not stat.S_ISREG(attached_before.st_mode) or stat.S_ISLNK(
        attached_before.st_mode
    ):
        raise ValueError("manifest publication target is unsafe")
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(name, flags, dir_fd=parent_fd)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_SH)
        opened = _validate_opened_regular_file(
            parent_fd, name, descriptor, "manifest publication target"
        )
        if (opened.st_dev, opened.st_ino) != (
            attached_before.st_dev,
            attached_before.st_ino,
        ):
            raise ValueError("manifest publication target changed while opened")
        payload = _read_descriptor_bytes(
            descriptor,
            limit=16 * 1024 * 1024,
            label="manifest publication target",
        )
        opened_after = _validate_opened_regular_file(
            parent_fd, name, descriptor, "manifest publication target"
        )
        if _stable_file_fingerprint(opened) != _stable_file_fingerprint(
            opened_after
        ):
            raise ValueError("manifest publication target changed while read")
        return opened_after, payload
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _manifest_publication_baseline(path: Path) -> dict[str, Any] | None:
    """Capture one safe draft inode before an explicit replacement build."""
    absolute = Path(os.path.abspath(path))
    _reject_symlink_components(absolute.parent, "manifest publication parent")
    if not absolute.parent.is_dir():
        return None
    parent_fd = _open_trusted_repository_directory(
        absolute.parent, "manifest publication parent directory"
    )
    try:
        try:
            attached = os.stat(
                absolute.name, dir_fd=parent_fd, follow_symlinks=False
            )
        except FileNotFoundError:
            return None
        try:
            attached, payload = _read_manifest_file_at(parent_fd, absolute.name)
        except ValueError as exc:
            raise ValueError(f"draft manifest replacement target is unsafe: {path}") from exc
        return {
            "device": attached.st_dev,
            "inode": attached.st_ino,
            "sha256": sha256_bytes(payload),
            "payload": payload,
        }
    finally:
        os.close(parent_fd)


def _publish_manifest_atomic(
    path: Path,
    payload: bytes,
    *,
    replace_baseline: dict[str, Any] | None,
    replace_draft: bool,
    replace_forbidden_paths: tuple[Path, ...] = (),
) -> None:
    """Publish a complete manifest atomically, with no-clobber as the default."""
    absolute = Path(os.path.abspath(path))
    _reject_symlink_components(absolute.parent, "manifest publication parent")
    parent_existed = absolute.parent.is_dir()
    absolute.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_components(absolute.parent, "manifest publication parent")
    if not parent_existed:
        ancestor_fd = _open_trusted_repository_directory(
            absolute.parent.parent, "manifest publication ancestor"
        )
        try:
            os.fsync(ancestor_fd)
        finally:
            os.close(ancestor_fd)
    parent_fd = _open_trusted_repository_directory(
        absolute.parent, "manifest publication parent directory"
    )
    temporary_name: str | None = None
    temporary_fd: int | None = None
    try:
        fcntl.flock(parent_fd, fcntl.LOCK_EX)
        if replace_draft:
            if replace_baseline is None:
                raise FileNotFoundError(
                    f"draft manifest replacement target does not exist: {path}"
                )
            try:
                attached, current = _read_manifest_file_at(parent_fd, absolute.name)
            except (FileNotFoundError, ValueError) as exc:
                raise FileExistsError(
                    "draft manifest changed during construction; refusing concurrent replacement"
                ) from exc
            if (
                (attached.st_dev, attached.st_ino)
                != (replace_baseline["device"], replace_baseline["inode"])
                or sha256_bytes(current) != replace_baseline["sha256"]
            ):
                raise FileExistsError(
                    "draft manifest changed during construction; refusing concurrent replacement"
                )
            if any(path_entry_exists(item) for item in replace_forbidden_paths):
                raise ValueError(
                    "refusing to replace a manifest after any run artifact or ledger exists"
                )
        for _ in range(64):
            candidate = f".{absolute.name}.publish-{os.urandom(12).hex()}.tmp"
            flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            try:
                temporary_fd = os.open(candidate, flags, 0o600, dir_fd=parent_fd)
            except FileExistsError:
                continue
            temporary_name = candidate
            break
        if temporary_fd is None or temporary_name is None:
            raise FileExistsError("could not allocate an exclusive manifest publication file")
        offset = 0
        while offset < len(payload):
            offset += os.write(temporary_fd, payload[offset:])
        os.fsync(temporary_fd)
        written = _validate_opened_regular_file(
            parent_fd,
            temporary_name,
            temporary_fd,
            "manifest publication file",
        )
        if (
            written.st_size != len(payload)
            or _read_descriptor_bytes(
                temporary_fd,
                limit=16 * 1024 * 1024,
                label="manifest publication file",
            )
            != payload
        ):
            raise ValueError("manifest publication file changed before commit")
        if replace_draft:
            os.replace(
                temporary_name,
                absolute.name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
            )
        else:
            _renameat2_noreplace(
                parent_fd,
                temporary_name,
                parent_fd,
                absolute.name,
                label=f"frozen manifest: {path}",
            )
        published = os.stat(
            absolute.name, dir_fd=parent_fd, follow_symlinks=False
        )
        if (published.st_dev, published.st_ino) != (
            written.st_dev,
            written.st_ino,
        ):
            raise ValueError("published manifest is not the completed publication file")
        temporary_name = None
        os.fsync(parent_fd)
    finally:
        if temporary_fd is not None:
            os.close(temporary_fd)
        if temporary_name is not None:
            try:
                os.unlink(temporary_name, dir_fd=parent_fd)
                os.fsync(parent_fd)
            except FileNotFoundError:
                pass
        try:
            fcntl.flock(parent_fd, fcntl.LOCK_UN)
        finally:
            os.close(parent_fd)


def unlink_file_durable(path: Path) -> None:
    """Remove one file and sync its parent without resolving through a swapped parent."""
    parent_fd = os.open(path.parent, _directory_open_flags())
    try:
        os.unlink(path.name, dir_fd=parent_fd)
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


def relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def path_entry_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _lexical_absolute_path(path: Path) -> Path:
    """Normalize dots without resolving any symlink component."""
    return Path(os.path.abspath(path))


def _validate_safe_owner_permissions(
    metadata: os.stat_result, label: str
) -> None:
    mode = stat.S_IMODE(metadata.st_mode)
    if metadata.st_uid != os.getuid():
        raise ValueError(f"{label} is not owned by the current user")
    if mode & 0o022:
        raise ValueError(f"{label} is group- or world-writable")


def _validate_no_posix_acl(
    descriptor: int, label: str, *, directory: bool
) -> None:
    """Reject access/default ACLs on the exact opened inode."""
    if not hasattr(os, "listxattr"):
        raise ValueError(f"{label} ACL safety cannot be established")
    try:
        names = {
            os.fsdecode(name) if isinstance(name, bytes) else name
            for name in os.listxattr(descriptor)
        }
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError(f"{label} ACL safety cannot be established") from exc
    forbidden = {"system.posix_acl_access"}
    if directory:
        forbidden.add("system.posix_acl_default")
    present = sorted(names & forbidden)
    if present:
        raise ValueError(f"{label} has a POSIX ACL: {', '.join(present)}")


def _validate_opened_directory(
    attached: os.stat_result,
    opened: os.stat_result,
    descriptor: int,
    label: str,
) -> None:
    if (
        not stat.S_ISDIR(attached.st_mode)
        or stat.S_ISLNK(attached.st_mode)
        or not stat.S_ISDIR(opened.st_mode)
    ):
        raise ValueError(f"{label} is not a real directory")
    if (opened.st_dev, opened.st_ino) != (attached.st_dev, attached.st_ino):
        raise ValueError(f"{label} changed while it was opened")
    _validate_safe_owner_permissions(attached, label)
    _validate_safe_owner_permissions(opened, label)
    _validate_no_posix_acl(descriptor, label, directory=True)


def _validate_opened_regular_file(
    directory_fd: int,
    name: str,
    descriptor: int,
    label: str,
) -> os.stat_result:
    """Validate the exact opened and still-attached witness inode."""
    attached = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    opened = os.fstat(descriptor)
    if (
        not stat.S_ISREG(attached.st_mode)
        or stat.S_ISLNK(attached.st_mode)
        or not stat.S_ISREG(opened.st_mode)
    ):
        raise ValueError(f"{label} is not a regular file")
    if attached.st_nlink != 1 or opened.st_nlink != 1:
        raise ValueError(f"{label} must have exactly one hard link")
    if (opened.st_dev, opened.st_ino) != (attached.st_dev, attached.st_ino):
        raise ValueError(f"{label} changed while it was opened")
    _validate_safe_owner_permissions(attached, label)
    _validate_safe_owner_permissions(opened, label)
    _validate_no_posix_acl(descriptor, label, directory=False)
    return opened


def _open_trusted_repository_directory(path: Path, label: str) -> int:
    """Open a repository directory through validated no-follow ancestors."""
    root = _lexical_absolute_path(ROOT)
    absolute = _lexical_absolute_path(path)
    try:
        relative_parts = absolute.relative_to(root).parts
    except ValueError as exc:
        raise ValueError(f"{label} escapes the repository trust anchor") from exc
    attached_root = root.lstat()
    descriptor = os.open(root, _directory_open_flags())
    try:
        _validate_opened_directory(
            attached_root,
            os.fstat(descriptor),
            descriptor,
            "repository trust anchor",
        )
        for component in relative_parts:
            attached = os.stat(
                component, dir_fd=descriptor, follow_symlinks=False
            )
            child = os.open(component, _directory_open_flags(), dir_fd=descriptor)
            try:
                _validate_opened_directory(
                    attached,
                    os.fstat(child),
                    child,
                    f"{label} component {component}",
                )
            except BaseException:
                os.close(child)
                raise
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _stable_file_fingerprint(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_uid,
        metadata.st_gid,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def file_record(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": relative(path), "sha256": sha256_bytes(data), "bytes": len(data)}


def attempt_intent_contract_version(manifest: dict[str, Any]) -> int:
    contract = manifest.get("attempt_intent_contract")
    if contract == ATTEMPT_INTENT_CONTRACT:
        return 2
    if contract == LEGACY_ATTEMPT_INTENT_CONTRACT:
        return 1
    return 0


def attempt_intent_enabled(manifest: dict[str, Any]) -> bool:
    return attempt_intent_contract_version(manifest) in {1, 2}


def attempt_claim_journal_enabled(manifest: dict[str, Any]) -> bool:
    return attempt_intent_contract_version(manifest) == 2


def attempt_intent_directory(manifest: dict[str, Any]) -> Path:
    return ROOT / str(manifest.get("bout_dir", "")) / ATTEMPT_INTENT_DIRECTORY


def attempt_intent_path(manifest: dict[str, Any], slot_id: str) -> Path:
    return attempt_intent_directory(manifest) / f"{_safe_path_component(slot_id, 'attempt-intent slot ID')}.json"


def attempt_claim_journal_path(manifest: dict[str, Any]) -> Path:
    return ROOT / str(manifest.get("bout_dir", "")) / ATTEMPT_CLAIM_JOURNAL


def _open_attempt_intent_directory(
    manifest: dict[str, Any], *, create: bool
) -> int | None:
    """Open the repository intent directory without following its final entries."""
    bout_fd = _open_attempt_bout_directory(manifest, create=create)
    if bout_fd is None:
        return None
    try:
        if create:
            try:
                os.mkdir(ATTEMPT_INTENT_DIRECTORY, mode=0o700, dir_fd=bout_fd)
            except FileExistsError:
                pass
            else:
                os.fsync(bout_fd)
        try:
            attached = os.stat(
                ATTEMPT_INTENT_DIRECTORY, dir_fd=bout_fd, follow_symlinks=False
            )
        except FileNotFoundError:
            return None
        if not stat.S_ISDIR(attached.st_mode) or stat.S_ISLNK(attached.st_mode):
            raise ValueError("attempt-intent path is not a real directory")
        directory_fd = os.open(
            ATTEMPT_INTENT_DIRECTORY, _directory_open_flags(), dir_fd=bout_fd
        )
        opened = os.fstat(directory_fd)
        try:
            _validate_opened_directory(
                attached,
                opened,
                directory_fd,
                "attempt-intent directory",
            )
        except ValueError:
            os.close(directory_fd)
            raise
        return directory_fd
    finally:
        os.close(bout_fd)


def _read_regular_file_snapshot_at(
    directory_fd: int,
    name: str,
    *,
    limit: int = 65536,
    label: str = "witness file",
) -> tuple[bytes, os.stat_result]:
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    attached_before = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    if not stat.S_ISREG(attached_before.st_mode) or stat.S_ISLNK(
        attached_before.st_mode
    ):
        raise ValueError(f"{label} is not a regular file")
    descriptor = os.open(name, flags, dir_fd=directory_fd)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_SH)
        opened_before = _validate_opened_regular_file(
            directory_fd, name, descriptor, label
        )
        if (attached_before.st_dev, attached_before.st_ino) != (
            opened_before.st_dev,
            opened_before.st_ino,
        ):
            raise ValueError(f"{label} changed while it was opened")
        payload = _read_descriptor_bytes(descriptor, limit=limit, label=label)
        opened_after = _validate_opened_regular_file(
            directory_fd, name, descriptor, label
        )
        if _stable_file_fingerprint(opened_before) != _stable_file_fingerprint(
            opened_after
        ):
            raise ValueError(f"{label} changed while it was read")
        return payload, opened_after
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _read_regular_file_at(
    directory_fd: int,
    name: str,
    *,
    limit: int = 65536,
    label: str = "witness file",
) -> bytes:
    payload, _metadata = _read_regular_file_snapshot_at(
        directory_fd, name, limit=limit, label=label
    )
    return payload


def _open_attempt_bout_directory(
    manifest: dict[str, Any], *, create: bool
) -> int | None:
    """Open the frozen bout directory without following a path component."""
    bout = Path(os.path.abspath(ROOT / str(manifest.get("bout_dir", ""))))
    try:
        bout.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError("attempt-claim bout directory escapes the repository") from exc
    _reject_symlink_components(bout, "attempt-claim bout directory")
    existed = path_entry_exists(bout)
    if create:
        bout.mkdir(parents=True, exist_ok=True)
        if not existed:
            parent_fd = _open_trusted_repository_directory(
                bout.parent, "attempt-claim bout parent"
            )
            try:
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
    if not path_entry_exists(bout):
        return None
    _reject_symlink_components(bout, "attempt-claim bout directory")
    return _open_trusted_repository_directory(
        bout, "attempt-claim bout directory"
    )


def _read_descriptor_bytes(
    descriptor: int, *, limit: int, label: str = "append-only claim journal"
) -> bytes:
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    length = 0
    while True:
        chunk = os.read(descriptor, min(65536, limit + 1 - length))
        if not chunk:
            break
        chunks.append(chunk)
        length += len(chunk)
        if length > limit:
            raise ValueError(f"{label} exceeds the safety size limit")
    return b"".join(chunks)


def _parse_attempt_claim_payload(
    manifest: dict[str, Any], payload: bytes
) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    all_slots = {
        slot["slot_id"]: slot
        for slot in [*(manifest.get("schedule") or []), *(manifest.get("reserve_slots") or [])]
    }
    if payload and not payload.endswith(b"\n"):
        errors.append("attempt-claim journal ends with an incomplete row")
    for line_number, raw_line in enumerate(payload.splitlines(keepends=True), start=1):
        if not raw_line.endswith(b"\n") or not raw_line.strip():
            errors.append(f"attempt-claim journal row {line_number} is incomplete or blank")
            continue
        try:
            record = json.loads(raw_line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            errors.append(f"attempt-claim journal row {line_number} is malformed")
            continue
        if not isinstance(record, dict):
            errors.append(f"attempt-claim journal row {line_number} is not an object")
            continue
        row_errors: list[str] = []
        slot_id = str(record.get("slot_id") or "")
        slot = all_slots.get(slot_id)
        if set(record) != ATTEMPT_CLAIM_FIELDS:
            row_errors.append("field set differs from the frozen schema")
        for good, label in (
            (record.get("schema_version") == 1, "schema version"),
            (record.get("record_kind") == "target-attempt-claim", "record kind"),
            (record.get("experiment_id") == manifest.get("experiment_id"), "experiment ID"),
            (record.get("manifest_freeze_id") == manifest.get("freeze_id"), "freeze ID"),
            (record.get("phase") == manifest.get("phase"), "phase"),
            (record.get("sequence") == line_number, "sequence"),
            (slot is not None, "slot ID"),
            (
                slot is not None and record.get("condition_id") == slot.get("condition_id"),
                "condition ID",
            ),
            (
                slot is not None and record.get("kind") == slot.get("kind", "primary"),
                "slot kind",
            ),
        ):
            if not good:
                row_errors.append(f"{label} mismatch")
        if slot is not None:
            try:
                expected_run_dir = relative(output_dir_for(manifest, slot))
            except (KeyError, OSError, ValueError):
                expected_run_dir = None
            if record.get("run_dir") != expected_run_dir:
                row_errors.append("run directory mismatch")
            expected_intent = str(
                Path(manifest["bout_dir"])
                / ATTEMPT_INTENT_DIRECTORY
                / f"{slot_id}.json"
            )
            if record.get("attempt_intent") != expected_intent:
                row_errors.append("attempt-intent path mismatch")
            if slot.get("kind", "primary") == "primary" and (
                record.get("replacement_for") is not None
                or record.get("exclusion_reason") is not None
            ):
                row_errors.append("primary claim contains replacement metadata")
        for key, label, pattern in (
            ("preflight_sha256", "preflight hash", r"[0-9a-f]{64}"),
            ("harness_commit", "harness commit", r"[0-9a-f]{40}"),
            ("command_sha256", "command hash", r"[0-9a-f]{64}"),
            ("attempt_intent_sha256", "attempt-intent hash", r"[0-9a-f]{64}"),
        ):
            if not re.fullmatch(pattern, str(record.get(key) or "")):
                row_errors.append(f"{label} is invalid")
        try:
            datetime.fromisoformat(str(record.get("created_at") or "").replace("Z", "+00:00"))
        except ValueError:
            row_errors.append("creation timestamp is invalid")
        if row_errors:
            errors.extend(
                f"attempt-claim journal row {line_number}: {issue}"
                for issue in row_errors
            )
        records.append(
            {
                "record": record,
                "path": str(Path(manifest["bout_dir"]) / ATTEMPT_CLAIM_JOURNAL),
                "sha256": sha256_bytes(raw_line),
                "line": line_number,
            }
        )
    slot_ids = [str(item["record"].get("slot_id")) for item in records]
    if len(slot_ids) != len(set(slot_ids)):
        errors.append("attempt-claim journal contains a duplicate slot")
    return records, errors


def read_attempt_claims(
    manifest: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Read the authoritative append-only claim journal without following it."""
    if not attempt_claim_journal_enabled(manifest):
        return [], []
    try:
        directory_fd = _open_attempt_bout_directory(manifest, create=False)
    except (OSError, ValueError) as exc:
        return [], [f"attempt-claim journal parent is unsafe: {type(exc).__name__}: {exc}"]
    if directory_fd is None:
        return [], []
    try:
        try:
            payload = _read_regular_file_at(
                directory_fd,
                ATTEMPT_CLAIM_JOURNAL,
                limit=16 * 1024 * 1024,
                label="attempt-claim journal",
            )
        except FileNotFoundError:
            return [], []
        except (OSError, ValueError) as exc:
            return [], [f"attempt-claim journal is unsafe or malformed: {type(exc).__name__}: {exc}"]
    finally:
        os.close(directory_fd)
    return _parse_attempt_claim_payload(manifest, payload)


def read_attempt_intents(
    manifest: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Read only exact, immutable slot claims; malformed state fails closed."""
    if not attempt_intent_enabled(manifest):
        return {}, []
    errors: list[str] = []
    records: dict[str, dict[str, Any]] = {}
    all_slots = {
        slot["slot_id"]: slot
        for slot in [*(manifest.get("schedule") or []), *(manifest.get("reserve_slots") or [])]
    }
    try:
        directory_fd = _open_attempt_intent_directory(manifest, create=False)
    except (OSError, ValueError) as exc:
        return {}, [f"attempt-intent directory is unsafe: {type(exc).__name__}: {exc}"]
    if directory_fd is None:
        return {}, []
    try:
        try:
            names = sorted(os.listdir(directory_fd))
        except OSError as exc:
            return {}, [f"attempt-intent directory is unreadable: {type(exc).__name__}"]
        if len(names) > len(all_slots):
            errors.append("attempt-intent directory contains more entries than frozen slots")
        for name in names:
            if not name.endswith(".json"):
                errors.append(f"unexpected attempt-intent entry: {name}")
                continue
            slot_id = name[:-5]
            slot = all_slots.get(slot_id)
            if slot is None or name != f"{slot_id}.json":
                errors.append(f"attempt intent references non-frozen slot: {name}")
                continue
            try:
                data = _read_regular_file_at(
                    directory_fd, name, label=f"attempt intent for {slot_id}"
                )
                record = json.loads(data)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                errors.append(
                    f"attempt intent for {slot_id} is unsafe or malformed: "
                    f"{type(exc).__name__}: {exc}"
                )
                continue
            if not isinstance(record, dict):
                errors.append(f"attempt intent for {slot_id} is not an object")
                continue
            record_errors: list[str] = []
            if set(record) != ATTEMPT_INTENT_FIELDS:
                record_errors.append("field set differs from the frozen schema")
            for good, label in (
                (record.get("schema_version") == 1, "schema version"),
                (record.get("record_kind") == "target-attempt-intent", "record kind"),
                (record.get("experiment_id") == manifest.get("experiment_id"), "experiment ID"),
                (record.get("manifest_freeze_id") == manifest.get("freeze_id"), "freeze ID"),
                (record.get("phase") == manifest.get("phase"), "phase"),
                (record.get("slot_id") == slot_id, "slot ID"),
                (record.get("condition_id") == slot.get("condition_id"), "condition ID"),
                (record.get("kind") == slot.get("kind", "primary"), "slot kind"),
                (
                    record.get("run_dir") == relative(output_dir_for(manifest, slot)),
                    "run directory",
                ),
            ):
                if not good:
                    record_errors.append(f"{label} mismatch")
            if not re.fullmatch(r"[0-9a-f]{64}", str(record.get("preflight_sha256") or "")):
                record_errors.append("preflight hash is invalid")
            if not re.fullmatch(r"[0-9a-f]{40}", str(record.get("harness_commit") or "")):
                record_errors.append("harness commit is invalid")
            if not re.fullmatch(r"[0-9a-f]{64}", str(record.get("command_sha256") or "")):
                record_errors.append("command hash is invalid")
            try:
                datetime.fromisoformat(str(record.get("created_at") or "").replace("Z", "+00:00"))
            except ValueError:
                record_errors.append("creation timestamp is invalid")
            if slot.get("kind", "primary") == "primary" and (
                record.get("replacement_for") is not None
                or record.get("exclusion_reason") is not None
            ):
                record_errors.append("primary intent contains replacement metadata")
            if record_errors:
                errors.extend(f"attempt intent for {slot_id}: {issue}" for issue in record_errors)
                continue
            records[slot_id] = {
                "record": record,
                "path": str(
                    Path(manifest["bout_dir"])
                    / ATTEMPT_INTENT_DIRECTORY
                    / name
                ),
                "sha256": sha256_bytes(data),
            }
    finally:
        os.close(directory_fd)
    return records, errors


def _attempt_intent_record(
    manifest: dict[str, Any],
    slot: dict[str, Any],
    preflight: dict[str, Any],
    command: list[str],
) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{64}", str(preflight.get("sha256") or "")):
        raise ValueError("attempt-intent preflight hash is invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", str(preflight.get("harness_commit") or "")):
        raise ValueError("attempt-intent harness commit is invalid")
    if not command or not all(isinstance(value, str) and value for value in command):
        raise ValueError("attempt-intent command is invalid")
    return {
        "schema_version": 1,
        "record_kind": "target-attempt-intent",
        "experiment_id": manifest["experiment_id"],
        "manifest_freeze_id": manifest["freeze_id"],
        "phase": manifest["phase"],
        "slot_id": slot["slot_id"],
        "condition_id": slot["condition_id"],
        "kind": slot.get("kind", "primary"),
        "run_dir": relative(output_dir_for(manifest, slot)),
        "replacement_for": slot.get("replacement_for"),
        "exclusion_reason": slot.get("exclusion_reason"),
        "created_at": utc_now(),
        "preflight_sha256": preflight["sha256"],
        "harness_commit": preflight["harness_commit"],
        "command_sha256": sha256_bytes(canonical_json(command)),
    }


def _parse_execution_ledger_payload(payload: bytes) -> list[dict[str, Any]]:
    if payload and not payload.endswith(b"\n"):
        raise ValueError("execution ledger ends with an incomplete row")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("execution ledger is not UTF-8") from exc
    ledger: list[dict[str, Any]] = []
    for number, line in enumerate(text.splitlines(keepends=True), start=1):
        if not line.endswith("\n") or not line.strip():
            raise ValueError(
                f"execution ledger row {number} is incomplete or blank"
            )
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"execution ledger is malformed at line {number}"
            ) from exc
        if not isinstance(row, dict):
            raise ValueError(f"execution ledger row {number} is not an object")
        ledger.append(row)
    return ledger


def _regular_file_snapshot(
    metadata: os.stat_result, payload: bytes
) -> dict[str, Any]:
    return {
        "exists": True,
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "mode": stat.S_IMODE(metadata.st_mode),
        "uid": metadata.st_uid,
        "gid": metadata.st_gid,
        "nlink": metadata.st_nlink,
        "size": metadata.st_size,
        "mtime_ns": metadata.st_mtime_ns,
        "ctime_ns": metadata.st_ctime_ns,
        "sha256": sha256_bytes(payload),
    }


def _read_execution_ledger_at(
    directory_fd: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        payload, metadata = _read_regular_file_snapshot_at(
            directory_fd,
            "EXECUTION.jsonl",
            limit=16 * 1024 * 1024,
            label="execution ledger",
        )
    except FileNotFoundError:
        return [], {"exists": False}
    return _parse_execution_ledger_payload(payload), _regular_file_snapshot(
        metadata, payload
    )


def _read_claim_ledger_at(directory_fd: int) -> list[dict[str, Any]]:
    ledger, _snapshot = _read_execution_ledger_at(directory_fd)
    return ledger


def read_execution_ledger(
    path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read one exact execution ledger through the strict witness contract."""
    absolute = Path(os.path.abspath(path))
    _reject_symlink_components(absolute.parent, "execution-ledger parent")
    try:
        parent_fd = _open_trusted_repository_directory(
            absolute.parent, "execution-ledger parent directory"
        )
    except FileNotFoundError:
        return [], {"exists": False}
    try:
        return _read_execution_ledger_at(parent_fd)
    finally:
        os.close(parent_fd)


def read_manifest_strict(
    path: Path,
    *,
    label: str = "experiment manifest",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read one exact manifest through the same no-follow trust boundary."""
    absolute = _lexical_absolute_path(path)
    _reject_symlink_components(absolute.parent, f"{label} parent")
    parent_fd = _open_trusted_repository_directory(
        absolute.parent, f"{label} parent directory"
    )
    try:
        payload, metadata = _read_regular_file_snapshot_at(
            parent_fd,
            absolute.name,
            limit=16 * 1024 * 1024,
            label=label,
        )
    finally:
        os.close(parent_fd)
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not strict UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not a JSON object")
    return value, _regular_file_snapshot(metadata, payload)


def _confirmatory_pending_attempt(
    ledger: list[dict[str, Any]],
) -> dict[str, Any] | None:
    pending: dict[str, Any] | None = None
    for row in ledger:
        if row.get("kind") == "primary":
            if pending is not None:
                return pending
            pending = row if row.get("analysis_eligible") is False else None
            continue
        if pending is None or row.get("replacement_for") != pending.get("slot_id"):
            continue
        pending = row if row.get("analysis_eligible") is False else None
    return pending


def _append_attempt_claim(
    manifest: dict[str, Any], intent_record: dict[str, Any], intent_sha256: str
) -> dict[str, Any]:
    """Append and sync the authoritative witness before creating the intent."""
    directory_fd = _open_attempt_bout_directory(manifest, create=True)
    assert directory_fd is not None
    flags = os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = None
    journal_existed = False
    try:
        try:
            attached_before = os.stat(
                ATTEMPT_CLAIM_JOURNAL,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            attached_before = None
        else:
            journal_existed = True
            if not stat.S_ISREG(attached_before.st_mode) or stat.S_ISLNK(
                attached_before.st_mode
            ):
                raise ValueError("attempt-claim journal is not a regular file")
        descriptor = os.open(
            ATTEMPT_CLAIM_JOURNAL, flags, 0o600, dir_fd=directory_fd
        )
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        opened_before = _validate_opened_regular_file(
            directory_fd,
            ATTEMPT_CLAIM_JOURNAL,
            descriptor,
            "attempt-claim journal",
        )
        existing_payload = _read_descriptor_bytes(
            descriptor,
            limit=16 * 1024 * 1024,
            label="attempt-claim journal",
        )
        existing, claim_errors = _parse_attempt_claim_payload(
            manifest, existing_payload
        )
        if claim_errors:
            raise ValueError("attempt-claim journal is invalid: " + "; ".join(claim_errors))
        slot_id = str(intent_record["slot_id"])
        if any(item["record"].get("slot_id") == slot_id for item in existing):
            raise FileExistsError(
                f"attempt-claim journal already contains {slot_id}"
            )
        ledger = _read_claim_ledger_at(directory_fd)
        claim_slot_ids = [str(item["record"].get("slot_id")) for item in existing]
        ledger_slot_ids = [str(row.get("slot_id")) for row in ledger]
        if claim_slot_ids != ledger_slot_ids:
            raise ValueError(
                "an unresolved or mismatched authoritative claim blocks another target attempt"
            )
        all_primaries = [slot["slot_id"] for slot in manifest.get("schedule") or []]
        claimed_primaries = [
            value for value in claim_slot_ids if value in set(all_primaries)
        ]
        if intent_record.get("kind") == "primary":
            if len(claimed_primaries) >= len(all_primaries) or slot_id != all_primaries[
                len(claimed_primaries)
            ]:
                raise ValueError(
                    "attempt-claim primary is not the next frozen sequence slot"
                )
        else:
            condition_reserves = [
                slot["slot_id"]
                for slot in manifest.get("reserve_slots") or []
                if slot.get("condition_id") == intent_record.get("condition_id")
            ]
            claimed_reserves = [
                value for value in claim_slot_ids if value in set(condition_reserves)
            ]
            if (
                len(claimed_reserves) >= len(condition_reserves)
                or slot_id != condition_reserves[len(claimed_reserves)]
            ):
                raise ValueError(
                    "attempt-claim reserve is not the next frozen reserve index"
                )
        if manifest.get("phase") == "confirmatory":
            pending = _confirmatory_pending_attempt(ledger)
            if intent_record.get("kind") == "primary" and pending is not None:
                raise ValueError(
                    f"analysis-ineligible attempt {pending.get('slot_id')} requires its next frozen reserve before a later primary"
                )
            if intent_record.get("kind") == "reserve" and (
                pending is None
                or intent_record.get("replacement_for") != pending.get("slot_id")
            ):
                raise ValueError(
                    "the next frozen reserve must replace the currently paused analysis-ineligible attempt"
                )
        intent_path = str(
            Path(manifest["bout_dir"])
            / ATTEMPT_INTENT_DIRECTORY
            / f"{slot_id}.json"
        )
        claim_record = {
            **intent_record,
            "record_kind": "target-attempt-claim",
            "sequence": len(existing) + 1,
            "attempt_intent": intent_path,
            "attempt_intent_sha256": intent_sha256,
        }
        payload = (json.dumps(claim_record, sort_keys=True) + "\n").encode()
        offset = 0
        while offset < len(payload):
            offset += os.write(descriptor, payload[offset:])
        os.fsync(descriptor)
        opened_after = _validate_opened_regular_file(
            directory_fd,
            ATTEMPT_CLAIM_JOURNAL,
            descriptor,
            "attempt-claim journal",
        )
        if (
            opened_before.st_dev,
            opened_before.st_ino,
        ) != (
            opened_after.st_dev,
            opened_after.st_ino,
        ):
            raise ValueError("attempt-claim journal changed during append")
        complete_payload = existing_payload + payload
        observed_payload = _read_descriptor_bytes(
            descriptor,
            limit=16 * 1024 * 1024,
            label="attempt-claim journal",
        )
        if observed_payload != complete_payload:
            raise ValueError("attempt-claim journal bytes changed during append")
        observed_claims, observed_errors = _parse_attempt_claim_payload(
            manifest, observed_payload
        )
        if (
            observed_errors
            or len(observed_claims) != len(existing) + 1
            or observed_claims[-1]["record"] != claim_record
        ):
            raise ValueError(
                "attempt-claim journal append did not produce one complete expected row"
            )
        verified_after = _validate_opened_regular_file(
            directory_fd,
            ATTEMPT_CLAIM_JOURNAL,
            descriptor,
            "attempt-claim journal",
        )
        if _stable_file_fingerprint(opened_after) != _stable_file_fingerprint(
            verified_after
        ):
            raise ValueError("attempt-claim journal changed during append verification")
        os.fsync(directory_fd)
        return {
            "record": claim_record,
            "path": str(Path(manifest["bout_dir"]) / ATTEMPT_CLAIM_JOURNAL),
            "sha256": sha256_bytes(payload),
            "line": claim_record["sequence"],
        }
    finally:
        if descriptor is not None:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)
        if not journal_existed:
            # Syncing even a rejected first creation makes the empty fail-closed
            # journal's directory entry durable.
            try:
                os.fsync(directory_fd)
            except OSError:
                pass
        os.close(directory_fd)


def _write_attempt_intent_record(
    manifest: dict[str, Any], record: dict[str, Any], payload: bytes
) -> tuple[str, str]:
    directory_fd = _open_attempt_intent_directory(manifest, create=True)
    assert directory_fd is not None
    name = f"{_safe_path_component(record['slot_id'], 'attempt-intent slot ID')}.json"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = None
    try:
        descriptor = os.open(name, flags, 0o600, dir_fd=directory_fd)
        offset = 0
        while offset < len(payload):
            offset += os.write(descriptor, payload[offset:])
        os.fsync(descriptor)
        os.fsync(directory_fd)
        written = _validate_opened_regular_file(
            directory_fd,
            name,
            descriptor,
            f"attempt intent for {record['slot_id']}",
        )
        if written.st_size != len(payload):
            raise ValueError("attempt intent changed before process-launch authorization")
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory_fd)
    path = str(Path(manifest["bout_dir"]) / ATTEMPT_INTENT_DIRECTORY / name)
    return path, sha256_bytes(payload)


def claim_attempt_intent(
    manifest: dict[str, Any],
    slot: dict[str, Any],
    preflight: dict[str, Any],
    command: list[str],
    *,
    test_only_crash_checkpoint: str | None = None,
) -> tuple[str, str]:
    """Durably acquire a frozen target slot before any driver process launch."""
    if not attempt_intent_enabled(manifest):
        raise ValueError("attempt-intent contract is not enabled")
    record = _attempt_intent_record(manifest, slot, preflight, command)
    payload = json.dumps(record, indent=2, ensure_ascii=False).encode() + b"\n"
    if attempt_claim_journal_enabled(manifest):
        _append_attempt_claim(manifest, record, sha256_bytes(payload))
        synthetic_crash_checkpoint(
            test_only_crash_checkpoint, "post_journal_pre_intent"
        )
    return _write_attempt_intent_record(manifest, record, payload)


def acquire_execution_lock(manifest: dict[str, Any]) -> int:
    """Serialize compliant runners on the frozen bout directory inode."""
    bout = Path(os.path.abspath(ROOT / str(manifest.get("bout_dir", ""))))
    try:
        bout.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError("execution-lock bout directory escapes the repository") from exc
    _reject_symlink_components(bout, "execution-lock bout directory")
    bout.mkdir(parents=True, exist_ok=True)
    _reject_symlink_components(bout, "execution-lock bout directory")
    descriptor = _open_trusted_repository_directory(
        bout, "execution-lock bout directory"
    )
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("another runner holds the experiment execution lock") from exc
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def default_conditions() -> list[dict[str, Any]]:
    """The convenience sample frozen for this experiment."""
    return [
        {
            "condition_id": "claude-code--claude-opus-5",
            "driver": "claude",
            "requested_model": "claude-opus-5",
            "model_argument": "claude-opus-5",
            "output_label": "claude-opus-5",
            "expected_model_identities": ["claude-opus-5"],
            "expected_model_aliases": [],
            "expected_providers": [],
            "expected_cli_version": "2.1.241 (Claude Code)",
            "expected_base_url": "https://api.anthropic.com",
            "model_env_expected": "absent",
            "effort": {"mode": "native_default", "cli_argument": None, "observed_value": "not_exposed"},
            "expected_effort_record": "native-default (flag omitted)",
            "expected_setting_sources": "project (fresh auth-only per-run home)",
            "instruction_configuration": "fresh auth-only per-run home; project setting source in a neutral scratch repository",
            "instruction_text_observability": "partial",
            "tool_configuration": "native default tools enabled",
        },
        {
            "condition_id": "codex--gpt-5.6-sol",
            "driver": "codex",
            "requested_model": "gpt-5.6-sol",
            "model_argument": "gpt-5.6-sol",
            "output_label": "gpt-5.6-sol-codex",
            "expected_model_identities": ["gpt-5.6-sol"],
            "expected_model_aliases": [],
            "expected_providers": [],
            "expected_cli_version": "codex-cli 0.149.0",
            "expected_base_url": "https://api.openai.com (native)",
            "effort": {"mode": "native_default", "cli_argument": None, "observed_value": "not_exposed"},
            "expected_effort_record": "codex-default",
            "expected_setting_sources": "none (--ignore-user-config, --ignore-rules, fresh auth-only HOME/CODEX_HOME)",
            "instruction_configuration": "fresh auth-only per-run HOME/CODEX_HOME with user config and rules disabled",
            "instruction_text_observability": "partial",
            "tool_configuration": "native default tools enabled; schemas opaque unless present in session rollout",
        },
        {
            "condition_id": "kimi-code--kimi-k3",
            "driver": "kimi",
            "requested_model": "kimi-k3",
            "model_argument": "arena/k3",
            "output_label": "kimi-k3-kimicode",
            "expected_model_identities": ["kimi-k3"],
            "expected_model_aliases": ["arena/k3"],
            "expected_providers": ["moonshot-platform"],
            "expected_cli_version": "kimi-code 0.27.0",
            "expected_base_url": "https://api.moonshot.ai/v1 (platform, metered)",
            "effort": {"mode": "native_default", "cli_argument": None, "observed_value": "max"},
            "expected_effort_record": "native-default (observed in wire journal)",
            "expected_setting_sources": "arena config.toml plus explicit empty skills directory",
            "instruction_configuration": "fresh per-run HOME copied from an exact config-only source; skills discovery overridden empty",
            "instruction_text_observability": "complete",
            "tool_configuration": "native default tools enabled",
        },
    ]


def current_amendments(*, include_amendment_5: bool = False) -> list[dict[str, Any]]:
    records = []
    amendment_records = [
        (AMENDMENT_1_ID, "technical_harness_compatibility", AMENDMENT_1_REL),
        (AMENDMENT_2_ID, "technical_crash_durability", AMENDMENT_2_REL),
        (AMENDMENT_3_ID, "technical_atomic_claims", AMENDMENT_3_REL),
        (
            AMENDMENT_4_ID,
            "technical_strict_launch_authorization",
            AMENDMENT_4_REL,
        ),
    ]
    if include_amendment_5:
        amendment_records.append(
            (AMENDMENT_5_ID, "technical_kimi_identity_compatibility", AMENDMENT_5_REL)
        )
    for amendment_id, kind, documentation_relative in amendment_records:
        documentation = ROOT / documentation_relative
        if not documentation.is_file() or documentation.is_symlink():
            raise ValueError(
                f"required amendment record is missing or unsafe: {documentation_relative}"
            )
        records.append(
            {
                "amendment_id": amendment_id,
                "kind": kind,
                "target_prompt_changed": False,
                "target_prompt_sha256": FROZEN_PROMPT_SHA256,
                "documentation": file_record(documentation),
            }
        )
    return records


def manifest_uses_amendment_5(manifest: dict[str, Any]) -> bool:
    return isinstance(manifest.get("smoke_replacement"), dict)


def frozen_core_relative(*, include_amendment_5: bool = False) -> list[str]:
    paths = list(FROZEN_CORE_RELATIVE)
    if include_amendment_5:
        paths.extend((AMENDMENT_5_REL, AMENDED_RUNBOOK_5_REL))
    return paths


def manifest_conditions_defaults(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    conditions = default_conditions()
    if not manifest_uses_amendment_5(manifest):
        return conditions
    for condition in conditions:
        if condition["condition_id"] == "kimi-code--kimi-k3":
            condition["expected_providers"] = ["kimi"]
    return [condition for condition in conditions if condition["condition_id"] == "kimi-code--kimi-k3"]


def _validated_bout_dir(value: str) -> str:
    candidate = Path(value)
    if candidate.is_absolute() or not candidate.parts or candidate.parts[0] != "bouts":
        raise ValueError("bout directory must be a repository-relative path under bouts/")
    try:
        resolved = (ROOT / candidate).resolve()
        resolved.relative_to((ROOT / "bouts").resolve())
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError("bout directory escapes the repository bouts directory") from exc
    if resolved == (ROOT / "bouts").resolve():
        raise ValueError("bout directory must name a child of bouts/")
    return str(candidate)


def _balanced_orders(condition_ids: list[str], repeats: int, seed: int) -> list[tuple[str, ...]]:
    """Return randomized complete-block orders with near-perfect position balance."""
    if repeats < 1:
        raise ValueError("repeats must be positive")
    permutations = list(itertools.permutations(condition_ids))
    quotient, remainder = divmod(repeats, len(permutations))
    orders = permutations * quotient
    if remainder:
        base = len(permutations) // len(condition_ids)
        best: list[tuple[tuple[str, ...], ...]] = []
        best_spread: int | None = None
        for candidate in itertools.combinations(permutations, remainder):
            counts = {cid: [base * quotient] * len(condition_ids) for cid in condition_ids}
            for order in candidate:
                for position, cid in enumerate(order):
                    counts[cid][position] += 1
            spread = max(max(v) - min(v) for v in counts.values())
            if best_spread is None or spread < best_spread:
                best_spread, best = spread, [candidate]
            elif spread == best_spread:
                best.append(candidate)
        chooser = random.Random(seed ^ 0xA53C91)
        orders.extend(chooser.choice(best))
    random.Random(seed).shuffle(orders)
    return orders


def smoke_continuation_state(predecessor_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Return content-addressed predecessor facts and its unattempted smoke suffix.

    The function verifies technical provenance only. It hashes response files as
    opaque bytes through the artifact contract and never returns their content.
    """
    expected_path = _lexical_absolute_path(ROOT / INITIAL_SMOKE_MANIFEST_REL)
    requested_path = _lexical_absolute_path(predecessor_path)
    if requested_path != expected_path:
        raise ValueError(f"smoke continuation must use the frozen predecessor {relative(expected_path)}")
    try:
        predecessor, _predecessor_snapshot = read_manifest_strict(
            requested_path, label="smoke predecessor manifest"
        )
    except (OSError, ValueError) as exc:
        raise ValueError("smoke predecessor manifest is unavailable or unsafe") from exc
    manifest_errors = validate_manifest(
        predecessor,
        check_files=False,
        allow_historical=True,
    )
    if manifest_errors:
        raise ValueError("historical smoke predecessor is invalid: " + "; ".join(manifest_errors))
    if predecessor.get("phase") != "smoke" or predecessor.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError("smoke predecessor belongs to a different phase or experiment")
    if len(predecessor.get("schedule") or []) != len(default_conditions()):
        raise ValueError("smoke predecessor does not contain the original one-call-per-condition block")
    ledger_path = requested_path.parent / "EXECUTION.jsonl"
    try:
        ledger, ledger_snapshot = read_execution_ledger(ledger_path)
    except (OSError, ValueError) as exc:
        raise ValueError(
            f"smoke predecessor execution ledger is unsafe: {type(exc).__name__}: {exc}"
        ) from exc
    if not ledger_snapshot["exists"]:
        raise ValueError("smoke predecessor execution ledger is missing or unsafe")
    ledger_errors = validate_execution_ledger(predecessor, ledger)
    ledger_errors.extend(validate_prior_attempt_provenance(predecessor, ledger))
    if ledger_errors:
        raise ValueError("smoke predecessor provenance is invalid: " + "; ".join(ledger_errors))
    if len(ledger) != 1 or ledger[0].get("kind") != "primary":
        raise ValueError("smoke continuation requires exactly one consumed primary call")
    consumed = ledger[0]
    first_slot = (predecessor.get("schedule") or [None])[0]
    if not isinstance(first_slot, dict) or consumed.get("slot_id") != first_slot.get("slot_id"):
        raise ValueError("consumed smoke call is not the exact first frozen predecessor slot")
    if consumed.get("condition_id") != "codex--gpt-5.6-sol":
        raise ValueError("the one consumed predecessor call is not the frozen Codex smoke slot")
    if consumed.get("smoke_excluded") is not True:
        raise ValueError("consumed predecessor call is not irreversibly smoke-excluded")
    if consumed.get("process_group_cleaned") is not True or consumed.get("staged_attempt_retained") is not False:
        raise ValueError("smoke predecessor lacks completed process and stage cleanup")
    consumed_record, consumed_errors = validate_run_provenance(predecessor, first_slot, consumed)
    if consumed_errors or consumed_record is None:
        raise ValueError(
            "consumed smoke run provenance is invalid: " + "; ".join(consumed_errors)
        )
    completion = consumed_record.get("completion") or {}
    if (
        completion.get("request_acceptance_observed") is not True
        or completion.get("target_response_activity_observed") is not True
        or completion.get("agent_exit") != 0
        or completion.get("output_present") is not True
        or completion.get("pre_request_transport_failure_observed") is not False
        or completion.get("timeout_exit") is not False
        or completion.get("structured_statuses") != ["turn.completed"]
    ):
        raise ValueError("predecessor ledger row does not prove a consumed target call")
    if (consumed_record.get("validity") or {}).get("smoke_excluded") is not True:
        raise ValueError("consumed run record is not smoke-excluded")
    consumed_run_dir = ROOT / str(consumed["run_dir"])
    for marker in ("target_started", "target_returned"):
        marker_path = consumed_run_dir / marker
        if marker_path.is_symlink() or not marker_path.is_file() or not marker_path.read_text().strip():
            raise ValueError(f"consumed smoke run lacks a safe nonempty {marker} marker")
    transcript, transcript_malformed = iter_jsonl(consumed_run_dir / "transcript.jsonl")
    if transcript_malformed:
        raise ValueError("consumed smoke transcript is malformed")
    transcript_shapes = Counter(
        (
            event.get("type"),
            (event.get("item") or {}).get("type")
            if isinstance(event.get("item"), dict)
            else None,
        )
        for event in transcript
    )
    if transcript_shapes != Counter(
        {
            ("thread.started", None): 1,
            ("turn.started", None): 1,
            ("item.completed", "agent_message"): 1,
            ("turn.completed", None): 1,
        }
    ):
        raise ValueError("consumed smoke transcript does not prove one clean completed target turn")
    attempted_slot_ids = [str(consumed["slot_id"])]
    remaining_slots = [
        dict(slot)
        for slot in (predecessor.get("schedule") or [])[len(attempted_slot_ids) :]
    ]
    if len(remaining_slots) != 2:
        raise ValueError("smoke continuation must contain exactly the two unattempted calls")
    predecessor_conditions = condition_map(predecessor)
    remaining_conditions = [predecessor_conditions[slot["condition_id"]] for slot in remaining_slots]
    artifact_path = ROOT / str(consumed.get("run_dir", "")) / "artifact_manifest.json"
    if not artifact_path.is_file() or artifact_path.is_symlink():
        raise ValueError("consumed smoke attempt lacks a safe artifact manifest")
    state = {
        "schema_version": 1,
        "predecessor_manifest": file_record(requested_path),
        "predecessor_freeze_id": predecessor["freeze_id"],
        "predecessor_ledger": file_record(ledger_path),
        "consumed_call_count": 1,
        "consumed_slot_ids": attempted_slot_ids,
        "consumed_artifact_manifests": [
            {"slot_id": consumed["slot_id"], **file_record(artifact_path)}
        ],
        "remaining_call_count": 2,
        "remaining_slot_ids": [slot["slot_id"] for slot in remaining_slots],
        "cumulative_smoke_call_cap": 3,
        "retries_allowed": False,
        "order_rule": "preserve the unattempted suffix of the predecessor randomized schedule",
    }
    return state, remaining_conditions, remaining_slots


def validate_smoke_call_budget(
    manifest: dict[str, Any],
    ledger: list[dict[str, Any]],
    *,
    next_slot: dict[str, Any] | None = None,
) -> list[str]:
    """Enforce the cumulative one-plus-two smoke budget without response access."""
    continuation = manifest.get("smoke_continuation")
    replacement = manifest.get("smoke_replacement")
    if continuation is None and replacement is None:
        return []
    if replacement is not None:
        errors: list[str] = []
        if replacement.get("calls_previously_consumed") != 2:
            errors.append("Amendment-5 replacement must account for exactly two prior smoke calls")
        if replacement.get("calls_in_manifest") != 1:
            errors.append("Amendment-5 replacement must freeze exactly one call")
        if replacement.get("cumulative_smoke_call_cap") != 3:
            errors.append("Amendment-5 replacement must retain the cumulative three-call cap")
        if replacement.get("retries_allowed") is not False:
            errors.append("Amendment-5 replacement must retain the no-retry rule")
        attempted = [row for row in ledger if isinstance(row, dict)]
        if attempted:
            errors.append("Amendment-5 replacement cannot resume a partially attempted replacement")
        if next_slot is not None:
            if next_slot.get("condition_id") != replacement.get("replaced_condition_id"):
                errors.append("Amendment-5 replacement slot is not the failed Kimi condition")
        return errors
    errors: list[str] = []
    consumed_conditions = {
        str(slot_id).partition("--")[2]
        for slot_id in continuation.get("consumed_slot_ids") or []
    }
    if attempt_claim_journal_enabled(manifest):
        claims, claim_errors = read_attempt_claims(manifest)
        intent_records, intent_errors = read_attempt_intents(manifest)
        errors.extend(claim_errors)
        errors.extend(intent_errors)
        claimed_slot_ids = {
            str(item["record"].get("slot_id")) for item in claims
        } | set(intent_records) | {
            str(row.get("slot_id"))
            for row in ledger
            if isinstance(row, dict) and row.get("kind") == "primary"
        }
        continuation_conditions = [
            str(slot.get("condition_id"))
            for slot in manifest.get("schedule") or []
            if slot["slot_id"] in claimed_slot_ids
        ]
    elif attempt_intent_enabled(manifest):
        intent_records, intent_errors = read_attempt_intents(manifest)
        errors.extend(intent_errors)
        claimed_slot_ids = set(intent_records) | {
            str(row.get("slot_id"))
            for row in ledger
            if isinstance(row, dict) and row.get("kind") == "primary"
        }
        continuation_conditions = [
            str(slot.get("condition_id"))
            for slot in manifest.get("schedule") or []
            if slot["slot_id"] in claimed_slot_ids
        ]
    else:
        continuation_conditions = [
            str(row.get("condition_id"))
            for row in ledger
            if isinstance(row, dict) and row.get("kind") == "primary"
        ]
    all_attempted = [*sorted(consumed_conditions), *continuation_conditions]
    if len(all_attempted) != len(set(all_attempted)):
        errors.append("cumulative smoke attempts contain a retried condition")
    total = int(continuation.get("consumed_call_count") or 0) + len(continuation_conditions)
    cap = int(continuation.get("cumulative_smoke_call_cap") or 0)
    if total > cap:
        errors.append("cumulative smoke call cap has already been exceeded")
    if next_slot is not None:
        next_condition = str(next_slot.get("condition_id"))
        if total >= cap:
            errors.append("cumulative smoke call cap blocks another target invocation")
        if next_condition in set(all_attempted):
            errors.append("next smoke slot would retry an already attempted condition")
    if set(all_attempted) - set(condition["condition_id"] for condition in default_conditions()):
        errors.append("cumulative smoke attempts include a non-frozen condition")
    return errors


def build_manifest(
    *,
    phase: str,
    output: Path,
    design: Path,
    analysis_script: Path,
    report_template: Path,
    repeats: int,
    seed: int,
    frozen_at: str,
    reserve_per_condition: int = 5,
    replace_draft: bool = False,
    bout_dir_override: str | None = None,
    smoke_continuation_from: Path | None = None,
    smoke_replacement_from: Path | None = None,
    test_only_allow_noncanonical_paths: bool = False,
) -> dict[str, Any]:
    require_strict_creation_umask("manifest publication")
    if phase not in {"smoke", "confirmatory"}:
        raise ValueError("phase must be smoke or confirmatory")
    draft_baseline = (
        _manifest_publication_baseline(output) if replace_draft else None
    )
    if phase == "confirmatory" and repeats < 10:
        raise ValueError("confirmatory manifests require at least 10 runs per condition")
    requested_bout_dir = bout_dir_override or f"bouts/{EXPERIMENT_ID}{'-smoke' if phase == 'smoke' else ''}"
    if not test_only_allow_noncanonical_paths:
        if replace_draft:
            raise ValueError(
                "the amendment-4 production manifests are immutable no-clobber publications"
            )
        expected_frozen_at = AMENDMENT_5_FROZEN_AT if smoke_replacement_from is not None else AMENDMENT_4_FROZEN_AT
        if frozen_at != expected_frozen_at:
            raise ValueError(
                f"the frozen timestamp must be {expected_frozen_at}"
            )
        if phase == "confirmatory":
            if smoke_continuation_from is not None:
                raise ValueError("confirmatory manifests cannot continue smoke")
            if (
                repeats != CONFIRMATORY_RUNS_PER_CONDITION
                or reserve_per_condition != CONFIRMATORY_RESERVES_PER_CONDITION
                or seed != CONFIRMATORY_RANDOM_SEED
            ):
                raise ValueError(
                    "the amendment-4 confirmatory manifest requires exactly "
                    f"runs={CONFIRMATORY_RUNS_PER_CONDITION}, "
                    f"reserves={CONFIRMATORY_RESERVES_PER_CONDITION}, and "
                    f"seed={CONFIRMATORY_RANDOM_SEED}"
                )
            expected_output = ROOT / AMENDED_CONFIRMATORY_BOUT_REL / "MANIFEST.json"
            if (
                _lexical_absolute_path(output)
                != _lexical_absolute_path(expected_output)
                or requested_bout_dir != AMENDED_CONFIRMATORY_BOUT_REL
            ):
                raise ValueError("the amended confirmatory manifest has one canonical output and bout path")
        elif smoke_replacement_from is not None:
            if phase != "smoke" or smoke_continuation_from is not None:
                raise ValueError("Kimi replacement must be a standalone smoke manifest")
            if repeats != 1 or reserve_per_condition != 0 or seed != SMOKE_REPLACEMENT_RANDOM_SEED:
                raise ValueError("the amendment-5 Kimi replacement requires one run, zero reserves, and its frozen seed")
            expected_output = ROOT / SMOKE_REPLACEMENT_BOUT_REL / "MANIFEST.json"
            if (
                _lexical_absolute_path(output) != _lexical_absolute_path(expected_output)
                or requested_bout_dir != SMOKE_REPLACEMENT_BOUT_REL
            ):
                raise ValueError("the amendment-5 replacement has one canonical output and bout path")
        elif smoke_continuation_from is None:
            raise ValueError("the initial smoke freeze is immutable; only its canonical continuation may be built")
        else:
            if (
                repeats != SMOKE_RUNS_PER_CONDITION
                or reserve_per_condition != SMOKE_RESERVES_PER_CONDITION
                or seed != SMOKE_RANDOM_SEED
            ):
                raise ValueError(
                    "the amendment-4 smoke continuation requires exactly "
                    f"runs={SMOKE_RUNS_PER_CONDITION}, "
                    f"reserves={SMOKE_RESERVES_PER_CONDITION}, and "
                    f"seed={SMOKE_RANDOM_SEED}"
                )
            expected_output = ROOT / SMOKE_CONTINUATION_BOUT_REL / "MANIFEST.json"
            if (
                _lexical_absolute_path(output)
                != _lexical_absolute_path(expected_output)
                or requested_bout_dir != SMOKE_CONTINUATION_BOUT_REL
            ):
                raise ValueError("the smoke continuation has one canonical output and bout path")
    prompt = ROOT / PROMPT_REL
    if sha256_path(prompt) != FROZEN_PROMPT_SHA256:
        raise ValueError("target prompt differs from the frozen exact prompt")
    continuation: dict[str, Any] | None = None
    if smoke_replacement_from is not None:
        if phase != "smoke" or repeats != 1 or reserve_per_condition != 0:
            raise ValueError("Kimi replacement requires phase=smoke, runs=1, and reserves=0")
        predecessor_path = _lexical_absolute_path(smoke_replacement_from)
        predecessor, _ = read_manifest_strict(predecessor_path, label="replacement predecessor manifest")
        if predecessor.get("freeze_id") != AMENDMENT_4_SMOKE_FREEZE_ID:
            raise ValueError("replacement predecessor is not the frozen Amendment-4 smoke manifest")
        conditions = manifest_conditions_defaults({"smoke_replacement": {}})
        schedule = [{
            "slot_id": "replacement-01--kimi-code--kimi-k3",
            "kind": "primary",
            "block": 1,
            "position": 1,
            "sequence": 1,
            "replicate": 1,
            "condition_id": "kimi-code--kimi-k3",
        }]
    elif smoke_continuation_from is not None:
        if phase != "smoke" or repeats != 1 or reserve_per_condition != 0:
            raise ValueError("smoke continuation requires phase=smoke, runs=1, and reserves=0")
        continuation, conditions, schedule = smoke_continuation_state(smoke_continuation_from)
    else:
        conditions = default_conditions()
        condition_ids = [c["condition_id"] for c in conditions]
        orders = _balanced_orders(condition_ids, repeats, seed)
        schedule = []
        sequence = 0
        for block, order in enumerate(orders, start=1):
            for position, condition_id in enumerate(order, start=1):
                sequence += 1
                schedule.append(
                    {
                        "slot_id": f"primary-{block:02d}--{condition_id}",
                        "kind": "primary",
                        "block": block,
                        "position": position,
                        "sequence": sequence,
                        "replicate": block,
                        "condition_id": condition_id,
                    }
                )
    condition_ids = [c["condition_id"] for c in conditions]
    reserves: list[dict[str, Any]] = []
    if phase == "confirmatory":
        for condition_id in condition_ids:
            for index in range(1, reserve_per_condition + 1):
                reserves.append(
                    {
                        "slot_id": f"reserve-{index:02d}--{condition_id}",
                        "kind": "reserve",
                        "reserve_index": index,
                        "replicate": repeats + index,
                        "condition_id": condition_id,
                        "replacement_for": None,
                    }
                )
    fixture_dir = ROOT / TASK_REL / "fixture"
    fixture_files = sorted(path for path in fixture_dir.rglob("*") if path.is_file())
    expected_fixture_path = (fixture_dir / ".gitkeep").resolve()
    if [path.resolve() for path in fixture_files] != [expected_fixture_path]:
        raise ValueError("neutral fixture must contain exactly its .gitkeep marker")
    supplied_core = {design.resolve(), analysis_script.resolve(), report_template.resolve()}
    expected_supplied = {
        (ROOT / f"bouts/{EXPERIMENT_ID}/DESIGN.md").resolve(),
        (ROOT / f"analysis/{EXPERIMENT_ID}/analyze.py").resolve(),
        (ROOT / f"analysis/{EXPERIMENT_ID}/REPORT_TEMPLATE.md").resolve(),
    }
    if supplied_core != expected_supplied:
        raise ValueError("manifest inputs must use the experiment's canonical design/analyzer/report paths")
    frozen_files = [*(ROOT / path for path in frozen_core_relative(include_amendment_5=smoke_replacement_from is not None)), *fixture_files]
    missing = [str(path) for path in frozen_files if not path.is_file()]
    if missing:
        raise ValueError(f"missing frozen input files: {missing}")
    bout_dir = _validated_bout_dir(requested_bout_dir)
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "phase": phase,
        "status": "excluded-smoke" if phase == "smoke" else "frozen-awaiting-explicit-user-approval",
        "frozen_at": frozen_at,
        "amendments": current_amendments(include_amendment_5=smoke_replacement_from is not None),
        "bout_dir": bout_dir,
        "task": {
            "path": TASK_REL,
            "target_prompt": prompt.read_text(),
            "prompt_sha256": sha256_path(prompt),
            "prompt_bytes": prompt.stat().st_size,
            "compatibility_amendments": [],
            "fixture_inventory": [file_record(path) for path in fixture_files],
            "setup_script": None,
        },
        "conditions": conditions,
        "sampling": {
            "valid_runs_per_condition": repeats,
            "fresh_process_and_session_per_slot": True,
            "serial_execution": True,
            "smoke_excluded_from_confirmatory": True,
            "reserve_slots_per_condition": reserve_per_condition if phase == "confirmatory" else 0,
            "adaptive_stopping": False,
        },
        "randomization": (
            {
                "algorithm": "continued predecessor randomized order; no rerandomization after technical halt",
                "seed": seed,
                "unit": "unattempted predecessor schedule suffix",
            }
            if continuation is not None
            else {
                "algorithm": "Python random.Random MT19937; complete blocks; position-balanced permutation selection",
                "seed": seed,
                "unit": "within-replicate condition order",
            }
        ),
        "schedule": schedule,
        "reserve_slots": reserves,
        "exclusions": {
            "replace_only": [
                "transport_or_service_failure_before_request_acceptance",
                "harness_crash_before_target_execution",
                "prompt_hash_mismatch",
                "wrong_model_or_frozen_configuration",
                "corrupted_or_missing_raw_artifact_due_to_harness",
                "external_termination_before_attributable_target_completion",
                "security_quarantine_after_secret_scan",
            ],
            "never_exclude": [
                "tool_or_subagent_call",
                "refusal_or_empty_target_output",
                "question_or_non_outline_prose",
                "invented_requirement_or_implementation_content",
                "normal_truncation",
                "target_driven_tool_loop_or_timeout",
            ],
        },
        "analysis": {
            "semantic_reviewers": 2,
            "third_adjudicator_for_every_disagreement": True,
            "primary_endpoints": [
                "A_ge_2",
                "B_ge_2",
                "C_eq_3",
                "D_ge_2",
                "full_gate_chain",
                "restraint_pass",
                "embargo_pass",
                "format_pass",
                "full_compliance",
            ],
            "interval": "two-sided 95% Wilson score interval",
            "embargo_clean_semantic_sensitivity": True,
            "no_omnibus_score_or_confirmatory_pairwise_ranking": True,
            "hidden_reasoning_scored": False,
        },
        "artifact_contract": {
            "raw_outputs_immutable": True,
            "required_common": COMMON_ARTIFACTS,
            "required_by_driver": RAW_ARTIFACTS,
            "derived": [*DERIVED_ARTIFACTS, "artifact_manifest.json"],
        },
        "frozen_inputs": [file_record(path) for path in frozen_files],
    }
    if not test_only_allow_noncanonical_paths:
        manifest["attempt_intent_contract"] = dict(ATTEMPT_INTENT_CONTRACT)
    if continuation is not None:
        manifest["smoke_continuation"] = continuation
        manifest["sampling"].update(
            {
                "calls_previously_consumed": continuation["consumed_call_count"],
                "calls_in_manifest": continuation["remaining_call_count"],
                "cumulative_smoke_call_cap": continuation["cumulative_smoke_call_cap"],
                "retries_allowed": False,
            }
        )
    if smoke_replacement_from is not None:
        predecessor, _ = read_manifest_strict(
            _lexical_absolute_path(smoke_replacement_from), label="replacement predecessor manifest"
        )
        manifest["smoke_replacement"] = {
            "schema_version": 1,
            "predecessor_manifest": file_record(_lexical_absolute_path(smoke_replacement_from)),
            "predecessor_freeze_id": predecessor["freeze_id"],
            "replaced_slot_id": "primary-01--kimi-code--kimi-k3",
            "replaced_condition_id": "kimi-code--kimi-k3",
            "replacement_reason": "wrong_model_or_frozen_configuration",
            "calls_previously_consumed": 2,
            "calls_in_manifest": 1,
            "cumulative_smoke_call_cap": 3,
            "retries_allowed": False,
            "identity_contract_change": "The Kimi wire provider label is frozen as kimi; endpoint, CLI, model alias, effort, and credential configuration are unchanged.",
        }
    if test_only_allow_noncanonical_paths:
        manifest["test_only_noncanonical_paths"] = True
    manifest["freeze_id"] = sha256_bytes(canonical_json(manifest))
    runtime_paths: tuple[Path, ...] = ()
    if replace_draft:
        if draft_baseline is None:
            raise FileNotFoundError(
                f"draft manifest replacement target does not exist: {output}"
            )
        try:
            prior = json.loads(draft_baseline["payload"])
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"draft manifest replacement target is unreadable: {type(exc).__name__}") from exc
        if prior.get("experiment_id") != EXPERIMENT_ID or prior.get("phase") != phase:
            raise ValueError("draft manifest replacement target belongs to a different experiment or phase")
        prior_bout = ROOT / str(prior.get("bout_dir", ""))
        runtime_paths = (
            prior_bout / "EXECUTION.jsonl",
            prior_bout / ATTEMPT_CLAIM_JOURNAL,
            prior_bout / ATTEMPT_INTENT_DIRECTORY,
            prior_bout / "ATTEMPT_FAILURES",
            prior_bout / "QUARANTINE",
            prior_bout / Path(TASK_REL).name,
        )
        if any(path.exists() or path.is_symlink() for path in runtime_paths):
            raise ValueError("refusing to replace a manifest after any run artifact or ledger exists")
    payload = json.dumps(manifest, indent=2, ensure_ascii=False).encode() + b"\n"
    _publish_manifest_atomic(
        output,
        payload,
        replace_baseline=draft_baseline,
        replace_draft=replace_draft,
        replace_forbidden_paths=runtime_paths,
    )
    return manifest


def condition_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {condition["condition_id"]: condition for condition in manifest["conditions"]}


def compute_freeze_id(manifest: dict[str, Any]) -> str:
    clone = dict(manifest)
    clone.pop("freeze_id", None)
    return sha256_bytes(canonical_json(clone))


def validate_smoke_replacement_metadata(
    manifest: dict[str, Any], *, check_files: bool
) -> list[str]:
    replacement = manifest.get("smoke_replacement")
    if not isinstance(replacement, dict):
        return ["Amendment-5 replacement metadata is missing"]
    errors: list[str] = []
    predecessor_record = replacement.get("predecessor_manifest") or {}
    predecessor_path = ROOT / str(predecessor_record.get("path", ""))
    expected_path = ROOT / SMOKE_CONTINUATION_BOUT_REL / "MANIFEST.json"
    if _lexical_absolute_path(predecessor_path) != _lexical_absolute_path(expected_path):
        errors.append("Amendment-5 predecessor is not the Amendment-4 smoke manifest")
        return errors
    if predecessor_record.get("sha256") != AMENDMENT_4_SMOKE_MANIFEST_SHA256:
        errors.append("Amendment-5 predecessor manifest hash is not the frozen Amendment-4 file hash")
    try:
        predecessor, _ = read_manifest_strict(predecessor_path, label="Amendment-5 predecessor manifest")
    except (OSError, ValueError) as exc:
        return [f"Amendment-5 predecessor manifest is unreadable: {type(exc).__name__}"]
    if predecessor.get("freeze_id") != AMENDMENT_4_SMOKE_FREEZE_ID:
        errors.append("Amendment-5 predecessor freeze ID is not the frozen Amendment-4 smoke freeze")
    predecessor_errors = validate_manifest(
        predecessor, check_files=False, allow_historical=True
    )
    errors.extend(f"Amendment-4 predecessor: {error}" for error in predecessor_errors)
    ledger_path = predecessor_path.parent / "EXECUTION.jsonl"
    try:
        ledger, _ = read_execution_ledger(ledger_path)
    except (OSError, ValueError) as exc:
        return errors + [f"Amendment-5 predecessor ledger is unreadable: {type(exc).__name__}"]
    if len(ledger) != 1:
        errors.append("Amendment-5 predecessor must contain exactly one recorded Kimi attempt")
    else:
        row = ledger[0]
        if row.get("condition_id") != "kimi-code--kimi-k3":
            errors.append("Amendment-5 predecessor row is not the Kimi attempt")
        if row.get("analysis_eligible") is not False or row.get("smoke_excluded") is not True:
            errors.append("Amendment-5 predecessor Kimi attempt is not excluded and ineligible")
        if "wrong_model_or_frozen_configuration" not in set(row.get("eligible_exclusion_reasons") or []):
            errors.append("Amendment-5 predecessor lacks the frozen-configuration exclusion reason")
    if replacement.get("predecessor_freeze_id") != predecessor.get("freeze_id"):
        errors.append("Amendment-5 predecessor freeze binding is inconsistent")
    if replacement.get("replaced_slot_id") != "primary-01--kimi-code--kimi-k3":
        errors.append("Amendment-5 replacement does not bind the failed Kimi slot")
    if replacement.get("replaced_condition_id") != "kimi-code--kimi-k3":
        errors.append("Amendment-5 replacement condition binding is invalid")
    if replacement.get("replacement_reason") != "wrong_model_or_frozen_configuration":
        errors.append("Amendment-5 replacement reason is not the recorded frozen-configuration failure")
    return errors


def validate_manifest(
    manifest: dict[str, Any],
    *,
    check_files: bool = True,
    allow_historical: bool = False,
) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != 1:
        errors.append("unsupported manifest schema")
    phase = manifest.get("phase")
    if phase not in {"smoke", "confirmatory"}:
        errors.append("invalid phase")
    if manifest.get("freeze_id") != compute_freeze_id(manifest):
        errors.append("freeze_id does not match manifest content")
    test_only_noncanonical = manifest.get("test_only_noncanonical_paths") is True
    uses_amendment_5 = manifest_uses_amendment_5(manifest)
    if test_only_noncanonical and os.environ.get("ARENA_SYNTHETIC_ONLY") != "1":
        errors.append("test-only noncanonical manifest is disabled outside synthetic tests")
    if not allow_historical and not test_only_noncanonical:
        bout_dir = manifest.get("bout_dir")
        sampling = manifest.get("sampling") or {}
        randomization = manifest.get("randomization") or {}
        expected_frozen_at = AMENDMENT_5_FROZEN_AT if uses_amendment_5 else AMENDMENT_4_FROZEN_AT
        if manifest.get("frozen_at") != expected_frozen_at:
            errors.append("current manifest does not use its frozen timestamp for the active amendment")
        if phase == "confirmatory" and bout_dir != AMENDED_CONFIRMATORY_BOUT_REL:
            errors.append("confirmatory manifest is outside its canonical amended bout directory")
        if phase == "confirmatory":
            if (
                sampling.get("valid_runs_per_condition")
                != CONFIRMATORY_RUNS_PER_CONDITION
            ):
                errors.append(
                    "current confirmatory manifest does not freeze exactly 20 runs per condition"
                )
            if (
                sampling.get("reserve_slots_per_condition")
                != CONFIRMATORY_RESERVES_PER_CONDITION
            ):
                errors.append(
                    "current confirmatory manifest does not freeze exactly 5 reserves per condition"
                )
            if randomization.get("seed") != CONFIRMATORY_RANDOM_SEED:
                errors.append(
                    "current confirmatory manifest does not use the frozen randomization seed"
                )
        if phase == "smoke" and uses_amendment_5:
            if manifest.get("bout_dir") != SMOKE_REPLACEMENT_BOUT_REL:
                errors.append("Amendment-5 replacement is outside its canonical bout directory")
            if manifest.get("smoke_continuation") is not None:
                errors.append("Amendment-5 replacement cannot also be a continuation")
            sampling = manifest.get("sampling") or {}
            if sampling.get("valid_runs_per_condition") != 1 or sampling.get("reserve_slots_per_condition") != 0:
                errors.append("Amendment-5 replacement must freeze one Kimi run and zero reserves")
            if (manifest.get("randomization") or {}).get("seed") != SMOKE_REPLACEMENT_RANDOM_SEED:
                errors.append("Amendment-5 replacement does not use its frozen seed")
        elif phase == "smoke" and manifest.get("smoke_continuation") is not None:
            if bout_dir != SMOKE_CONTINUATION_BOUT_REL:
                errors.append("smoke continuation is outside its canonical bout directory")
            if sampling.get("valid_runs_per_condition") != SMOKE_RUNS_PER_CONDITION:
                errors.append(
                    "current smoke continuation does not freeze exactly one run per condition"
                )
            if sampling.get("reserve_slots_per_condition") != SMOKE_RESERVES_PER_CONDITION:
                errors.append("current smoke continuation must freeze zero reserves")
            if randomization.get("seed") != SMOKE_RANDOM_SEED:
                errors.append(
                    "current smoke continuation does not use the frozen randomization seed"
                )
        if phase == "smoke" and manifest.get("smoke_continuation") is None and not uses_amendment_5:
            errors.append("current smoke manifests must be canonical continuations of the immutable initial smoke")
    if not allow_historical:
        try:
            expected_amendments = current_amendments(include_amendment_5=uses_amendment_5)
        except (OSError, ValueError) as exc:
            errors.append(f"current amendment record is unavailable: {exc}")
        else:
            if manifest.get("amendments") != expected_amendments:
                errors.append("manifest does not contain the exact current technical amendment record")
    intent_contract = manifest.get("attempt_intent_contract")
    if intent_contract is None:
        if not allow_historical and not test_only_noncanonical:
            errors.append("production manifest lacks the crash-durable attempt-intent contract")
    elif intent_contract == LEGACY_ATTEMPT_INTENT_CONTRACT:
        if (
            not allow_historical
            and manifest.get("freeze_id") not in LEGACY_ATTEMPT_MANIFEST_FREEZE_IDS
        ):
            errors.append(
                "legacy attempt-intent contract is restricted to immutable amendment-2 freezes"
            )
    elif intent_contract != ATTEMPT_INTENT_CONTRACT:
        errors.append("attempt-intent contract differs from the frozen crash-durability contract")
    task = manifest.get("task") or {}
    prompt_path = ROOT / str(task.get("path", "")) / "PROMPT.md"
    if task.get("prompt_sha256") != FROZEN_PROMPT_SHA256:
        errors.append("manifest prompt hash is not the frozen target hash")
    if task.get("compatibility_amendments") != []:
        errors.append("target-prompt amendment present; freeze a new design version before running")
    if task.get("setup_script") is not None:
        errors.append("neutral response-only task must not have a setup script")
    if check_files:
        if not prompt_path.is_file():
            errors.append("target prompt file missing")
        else:
            data = prompt_path.read_bytes()
            if sha256_bytes(data) != task.get("prompt_sha256"):
                errors.append("target prompt file hash mismatch")
            if data.decode() != task.get("target_prompt"):
                errors.append("manifest target prompt text mismatch")
            if len(data) != task.get("prompt_bytes"):
                errors.append("manifest target prompt byte count mismatch")
        frozen_records = manifest.get("frozen_inputs") or []
        frozen_paths = [rec.get("path") for rec in frozen_records if isinstance(rec, dict)]
        expected_frozen_paths = set(frozen_core_relative(include_amendment_5=uses_amendment_5)) | {
            item.get("path") for item in task.get("fixture_inventory") or [] if isinstance(item, dict)
        }
        if len(frozen_paths) != len(set(frozen_paths)) or set(frozen_paths) != expected_frozen_paths:
            errors.append("frozen input inventory differs from the required treatment surface")
        for rec in frozen_records:
            if not isinstance(rec, dict):
                errors.append("malformed frozen input record")
                continue
            path = ROOT / rec.get("path", "")
            if not path.is_file():
                errors.append(f"frozen input missing: {rec.get('path')}")
            elif sha256_path(path) != rec.get("sha256") or path.stat().st_size != rec.get("bytes"):
                errors.append(f"frozen input drift: {rec.get('path')}")
        fixture_dir = ROOT / str(task.get("path", "")) / "fixture"
        actual_fixture = {
            relative(path): (sha256_path(path), path.stat().st_size)
            for path in fixture_dir.rglob("*")
            if path.is_file()
        } if fixture_dir.is_dir() else {}
        frozen_fixture = {
            item.get("path"): (item.get("sha256"), item.get("bytes"))
            for item in task.get("fixture_inventory") or []
            if isinstance(item, dict)
        }
        if actual_fixture != frozen_fixture:
            errors.append("neutral fixture inventory or content drift")
        if set(actual_fixture) != {f"{TASK_REL}/fixture/.gitkeep"}:
            errors.append("neutral fixture must contain exactly .gitkeep and no instruction or product files")
        setup_path = ROOT / str(task.get("path", "")) / "setup.sh"
        if task.get("setup_script") is None and setup_path.exists():
            errors.append("unexpected task setup.sh would change the frozen target workspace")
    conditions = condition_map(manifest) if manifest.get("conditions") else {}
    if len(conditions) != len(manifest.get("conditions") or []):
        errors.append("duplicate condition_id")
    default_by_id = {
        condition["condition_id"]: condition
        for condition in manifest_conditions_defaults(manifest)
    }
    for condition_id, condition in conditions.items():
        if condition_id not in default_by_id or condition != default_by_id.get(condition_id):
            errors.append(f"condition {condition_id} differs from the frozen default condition")
        if condition.get("instruction_text_observability") not in {"complete", "partial"}:
            errors.append(f"condition {condition_id} has invalid instruction-text observability")
    continuation = manifest.get("smoke_continuation")
    if phase == "confirmatory" and set(conditions) != set(default_by_id):
        errors.append("confirmatory manifest must contain every frozen condition")
    if phase == "smoke" and continuation is None and not uses_amendment_5 and set(conditions) != set(default_by_id):
        errors.append("initial smoke manifest must contain every frozen condition")
    if uses_amendment_5 and set(conditions) != {"kimi-code--kimi-k3"}:
        errors.append("Amendment-5 replacement must contain only the Kimi condition")
    if uses_amendment_5:
        errors.extend(
            validate_smoke_replacement_metadata(manifest, check_files=check_files)
        )
    if continuation is not None and phase != "smoke":
        errors.append("only a smoke manifest may contain continuation metadata")
    if check_files:
        try:
            configuration_lock = load_json(ROOT / CONFIG_LOCK_REL)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"configuration lock unreadable: {exc}")
        else:
            locked_conditions = configuration_lock.get("conditions") or {}
            if configuration_lock.get("schema_version") != 1 or not set(conditions).issubset(set(locked_conditions)):
                errors.append("configuration lock does not cover frozen conditions")
    repeats = (manifest.get("sampling") or {}).get("valid_runs_per_condition")
    if not isinstance(repeats, int) or repeats < 1:
        errors.append("invalid valid_runs_per_condition")
    elif phase == "confirmatory" and repeats < 10:
        errors.append("confirmatory runs per condition below 10")
    slots = manifest.get("schedule") or []
    slot_ids = [slot.get("slot_id") for slot in slots]
    if len(slot_ids) != len(set(slot_ids)):
        errors.append("duplicate primary slot_id")
    if continuation is not None:
        if not check_files:
            predecessor_record = continuation.get("predecessor_manifest") or {}
            predecessor_path = ROOT / str(predecessor_record.get("path", ""))
            if predecessor_record.get("sha256") != (
                sha256_path(predecessor_path) if predecessor_path.is_file() else None
            ):
                errors.append("smoke continuation predecessor manifest anchor is invalid")
        else:
            try:
                expected_continuation, expected_conditions, expected_slots = smoke_continuation_state(
                    ROOT / str((continuation.get("predecessor_manifest") or {}).get("path", ""))
                )
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"smoke continuation provenance is invalid: {exc}")
            else:
                if continuation != expected_continuation:
                    errors.append("smoke continuation metadata differs from predecessor evidence")
                if manifest.get("conditions") != expected_conditions:
                    errors.append("smoke continuation conditions are not the unattempted predecessor suffix")
                if slots != expected_slots:
                    errors.append("smoke continuation schedule is not the unattempted predecessor suffix")
        sampling = manifest.get("sampling") or {}
        expected_sampling = {
            "calls_previously_consumed": 1,
            "calls_in_manifest": 2,
            "cumulative_smoke_call_cap": 3,
            "retries_allowed": False,
        }
        for key, value in expected_sampling.items():
            if sampling.get(key) != value:
                errors.append(f"smoke continuation sampling field {key} is invalid")
        if len(slots) != 2 or set(slot_ids) != set(continuation.get("remaining_slot_ids") or []):
            errors.append("smoke continuation does not contain exactly the two remaining slots")
        consumed_conditions = {
            str(slot_id).partition("--")[2]
            for slot_id in continuation.get("consumed_slot_ids") or []
        }
        if set(conditions) & consumed_conditions:
            errors.append("smoke continuation includes a consumed condition")
        if set(conditions) | consumed_conditions != set(default_by_id):
            errors.append("consumed and remaining smoke conditions do not form the original three-call set")
    elif uses_amendment_5:
        expected_slots = [{
            "slot_id": "replacement-01--kimi-code--kimi-k3",
            "kind": "primary",
            "block": 1,
            "position": 1,
            "sequence": 1,
            "replicate": 1,
            "condition_id": "kimi-code--kimi-k3",
        }]
        if slots != expected_slots:
            errors.append("Amendment-5 replacement schedule differs from its frozen one-slot schedule")
    elif conditions and isinstance(repeats, int):
        seed = (manifest.get("randomization") or {}).get("seed")
        if isinstance(seed, int):
            expected_slots: list[dict[str, Any]] = []
            sequence = 0
            for block, order in enumerate(_balanced_orders(list(conditions), repeats, seed), start=1):
                for position, condition_id in enumerate(order, start=1):
                    sequence += 1
                    expected_slots.append(
                        {
                            "slot_id": f"primary-{block:02d}--{condition_id}",
                            "kind": "primary",
                            "block": block,
                            "position": position,
                            "sequence": sequence,
                            "replicate": block,
                            "condition_id": condition_id,
                        }
                    )
            if slots != expected_slots:
                errors.append("primary schedule differs from the deterministic frozen randomization")
        else:
            errors.append("randomization seed must be an integer")
        by_condition = Counter(slot.get("condition_id") for slot in slots)
        for cid in conditions:
            if by_condition[cid] != repeats:
                errors.append(f"condition {cid} has {by_condition[cid]} primary slots, expected {repeats}")
        by_block: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for slot in slots:
            by_block[slot.get("block")].append(slot)
        for block, block_slots in by_block.items():
            if {slot.get("condition_id") for slot in block_slots} != set(conditions):
                errors.append(f"block {block} is not a complete condition block")
            positions = sorted(slot.get("position") for slot in block_slots)
            if positions != list(range(1, len(conditions) + 1)):
                errors.append(f"block {block} positions are invalid")
        if phase == "confirmatory":
            position_counts: dict[str, Counter[int]] = defaultdict(Counter)
            for slot in slots:
                position_counts[slot["condition_id"]][slot["position"]] += 1
            for cid, counts in position_counts.items():
                values = [counts[p] for p in range(1, len(conditions) + 1)]
                if max(values) - min(values) > 1:
                    errors.append(f"condition {cid} order positions are not balanced: {values}")
    reserve_ids = [slot.get("slot_id") for slot in manifest.get("reserve_slots") or []]
    if len(reserve_ids) != len(set(reserve_ids)) or set(reserve_ids) & set(slot_ids):
        errors.append("duplicate or overlapping reserve slot_id")
    if phase == "smoke" and (manifest.get("reserve_slots") or []):
        errors.append("smoke manifest must not contain replacement slots")
    if phase == "confirmatory" and isinstance(repeats, int):
        reserve_count = (manifest.get("sampling") or {}).get("reserve_slots_per_condition")
        expected_reserves = [
            {
                "slot_id": f"reserve-{index:02d}--{condition_id}",
                "kind": "reserve",
                "reserve_index": index,
                "replicate": repeats + index,
                "condition_id": condition_id,
                "replacement_for": None,
            }
            for condition_id in conditions
            for index in range(1, int(reserve_count or 0) + 1)
        ]
        if (manifest.get("reserve_slots") or []) != expected_reserves:
            errors.append("reserve schedule differs from the deterministic frozen construction")
    return errors


def validate_historical_smoke_sources(
    manifest_path: Path,
    manifest: dict[str, Any],
) -> tuple[str | None, list[str]]:
    """Verify the one superseded smoke freeze from its anchored Git commit."""
    errors: list[str] = []
    expected_manifest = _lexical_absolute_path(ROOT / INITIAL_SMOKE_MANIFEST_REL)
    resolved_manifest = _lexical_absolute_path(manifest_path)
    if resolved_manifest != expected_manifest:
        errors.append("historical mode is restricted to the canonical initial smoke manifest")
    try:
        read_manifest_strict(
            resolved_manifest, label="historical smoke manifest"
        )
    except (OSError, ValueError) as exc:
        return None, [
            f"historical smoke manifest is unavailable or unsafe: {type(exc).__name__}: {exc}"
        ]
    if manifest.get("freeze_id") != INITIAL_SMOKE_FREEZE_ID:
        errors.append("historical mode is restricted to the recorded initial smoke freeze")
    continuation_path = ROOT / SMOKE_CONTINUATION_BOUT_REL / "MANIFEST.json"
    if not continuation_path.is_file() or continuation_path.is_symlink():
        errors.append("canonical continuation manifest is unavailable to anchor historical verification")
    else:
        try:
            continuation_manifest, _continuation_snapshot = read_manifest_strict(
                continuation_path, label="canonical continuation manifest"
            )
        except (OSError, ValueError) as exc:
            errors.append(f"canonical continuation manifest is unreadable: {type(exc).__name__}")
        else:
            continuation_errors = validate_manifest(
                continuation_manifest,
                check_files=False,
                allow_historical=False,
            )
            errors.extend(
                f"canonical continuation: {error}" for error in continuation_errors
            )
            predecessor_record = (
                continuation_manifest.get("smoke_continuation") or {}
            ).get("predecessor_manifest") or {}
            if predecessor_record != file_record(resolved_manifest):
                errors.append("canonical continuation does not anchor this historical manifest")
    ledger_path = resolved_manifest.parent / "EXECUTION.jsonl"
    try:
        ledger, _ledger_snapshot = read_execution_ledger(ledger_path)
    except (OSError, ValueError) as exc:
        errors.append(
            f"historical smoke ledger is unsafe or malformed: {type(exc).__name__}: {exc}"
        )
        return None, errors
    if len(ledger) != 1:
        errors.append("historical smoke ledger cannot identify one recorded harness commit")
        return None, errors
    commit = str(((ledger[0].get("preflight") or {}).get("harness_commit") or ""))
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        errors.append("historical smoke ledger lacks a full Git commit identifier")
        return None, errors

    def git_blob(path: str) -> bytes | None:
        completed = subprocess.run(
            ["git", "show", f"{commit}:{path}"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return completed.stdout if completed.returncode == 0 else None

    manifest_blob = git_blob(INITIAL_SMOKE_MANIFEST_REL)
    if manifest_blob is None or sha256_bytes(manifest_blob) != sha256_path(resolved_manifest):
        errors.append("historical smoke manifest does not match its recorded Git commit")
    for record in manifest.get("frozen_inputs") or []:
        if not isinstance(record, dict):
            errors.append("historical frozen-input record is malformed")
            continue
        path = str(record.get("path") or "")
        blob = git_blob(path)
        if (
            blob is None
            or sha256_bytes(blob) != record.get("sha256")
            or len(blob) != record.get("bytes")
        ):
            errors.append(f"historical frozen input differs at recorded commit: {path}")
    return commit, errors


def iter_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[int]]:
    events: list[dict[str, Any]] = []
    malformed: list[int] = []
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return events, [0]
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            malformed.append(number)
            continue
        if isinstance(event, dict):
            event["_line"] = number
            events.append(event)
        else:
            malformed.append(number)
    return events, malformed


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        for key in ("text", "output_text", "input_text"):
            if isinstance(block.get(key), str):
                parts.append(block[key])
                break
    return "".join(parts)


def extract_final_output(driver: str, run_dir: Path, events: list[dict[str, Any]]) -> tuple[str, str]:
    if driver == "claude":
        result_events: list[dict[str, Any]] = []
        result_path = run_dir / "result.json"
        if result_path.is_file() and result_path.read_text().strip():
            try:
                parsed = json.loads(result_path.read_text())
                if isinstance(parsed, dict):
                    result_events.append(parsed)
            except json.JSONDecodeError:
                pass
        result_events.extend(event for event in events if event.get("type") == "result")
        for event in reversed(result_events):
            if isinstance(event.get("result"), str):
                return event["result"], "result_event.result"
        return "", "missing_result_event"
    if driver == "codex":
        path = run_dir / "last_message.txt"
        return (path.read_text(errors="replace"), "last_message.txt") if path.is_file() else ("", "missing_last_message")
    if driver == "kimi":
        for event in reversed(events):
            if event.get("role") == "assistant" and not (event.get("tool_calls") or []):
                text = _content_text(event.get("content"))
                if text:
                    return text, f"transcript.jsonl:{event['_line']}"
        return "", "missing_terminal_assistant_content"
    raise ValueError(f"unknown driver: {driver}")


def _event_name_from_input(item: dict[str, Any]) -> str:
    for key in ("name", "tool_name", "command"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value if key != "command" else "command_execution"
        if isinstance(value, list) and value:
            return "command_execution"
    return str(item.get("type") or item.get("item_type") or "unknown_tool")


def _call_arguments(value: Any) -> Any:
    """Keep observable call arguments for deterministic subtype coding."""
    if value is None or isinstance(value, (str, int, float, bool, list, dict)):
        return value
    return str(value)


def detect_tool_events(driver: str, events: list[dict[str, Any]], run_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    calls: dict[str, dict[str, Any]] = {}
    unknown: list[str] = []
    if driver == "claude":
        for event in events:
            event_type = event.get("type")
            if event_type not in CLAUDE_TOP_LEVEL_EVENTS:
                unknown.append(f"transcript.jsonl:{event['_line']}:unknown top-level event {event_type!r}")
                continue
            if event_type == "system":
                if event.get("subtype") not in CLAUDE_SYSTEM_SUBTYPES:
                    unknown.append(
                        f"transcript.jsonl:{event['_line']}:unknown system subtype {event.get('subtype')!r}"
                    )
                continue
            if event_type not in {"assistant", "user"}:
                continue
            message = event.get("message")
            if not isinstance(message, dict) or not isinstance(message.get("content"), list):
                unknown.append(f"transcript.jsonl:{event['_line']}:malformed {event_type} message envelope")
                continue
            for index, block in enumerate(message["content"]):
                if not isinstance(block, dict):
                    unknown.append(f"transcript.jsonl:{event['_line']}:malformed {event_type} content block")
                    continue
                block_type = block.get("type")
                if block_type in CLAUDE_ACTION_BLOCKS:
                    event_id = str(block.get("id") or f"line-{event['_line']}-block-{index}")
                    calls[event_id] = {
                        "event_id": event_id,
                        "source": "transcript.jsonl",
                        "line": event["_line"],
                        "name": str(block.get("name") or block_type),
                        "event_type": block_type,
                        "arguments": _call_arguments(block.get("input")),
                    }
                elif block_type == "tool_result":
                    event_id = str(block.get("tool_use_id") or f"line-{event['_line']}-block-{index}")
                    if event_id not in calls:
                        calls[event_id] = {
                            "event_id": event_id,
                            "source": "transcript.jsonl",
                            "line": event["_line"],
                            "name": "observed_tool_result_without_call",
                            "event_type": "tool_result",
                            "arguments": None,
                        }
                elif block_type not in CLAUDE_PASSIVE_BLOCKS:
                    unknown.append(
                        f"transcript.jsonl:{event['_line']}:unknown {event_type} content type {block_type!r}"
                    )
            parent = event.get("parent_tool_use_id") if event_type == "assistant" else None
            if parent and str(parent) not in calls:
                calls[str(parent)] = {
                    "event_id": str(parent),
                    "source": "transcript.jsonl",
                    "line": event["_line"],
                    "name": "nested_agent_activity",
                    "event_type": "parent_tool_use_id",
                    "arguments": None,
                }
    elif driver == "codex":
        for event in events:
            envelope_type = event.get("type")
            if envelope_type not in CODEX_TOP_LEVEL_EVENTS:
                unknown.append(f"transcript.jsonl:{event['_line']}:unknown top-level event {envelope_type!r}")
                continue
            if envelope_type not in {"item.started", "item.updated", "item.completed"}:
                continue
            item = event.get("item")
            if not isinstance(item, dict):
                unknown.append(f"transcript.jsonl:{event['_line']}:malformed item envelope")
                continue
            item_type = item.get("type") or item.get("item_type")
            if item_type in PASSIVE_CODEX_ITEMS:
                continue
            if not item_type:
                unknown.append(f"transcript.jsonl:{event['_line']}:missing item type")
                continue
            if item_type not in ACTIVE_CODEX_ITEMS:
                unknown.append(f"transcript.jsonl:{event['_line']}:unknown item type {item_type!r}")
            event_id = str(item.get("id") or f"line-{event['_line']}")
            calls[event_id] = {
                "event_id": event_id,
                "source": "transcript.jsonl",
                "line": event["_line"],
                "name": _event_name_from_input(item),
                "event_type": str(item_type),
                "arguments": _call_arguments(
                    item.get("arguments")
                    if item.get("arguments") is not None
                    else item.get("command")
                    if item.get("command") is not None
                    else item.get("changes")
                ),
            }
        session_path = run_dir / "session.jsonl"
        session_events, session_bad = iter_jsonl(session_path) if session_path.is_file() else ([], [])
        unknown.extend(f"session.jsonl:{line}:malformed" for line in session_bad)
        for event in session_events:
            envelope_type = event.get("type")
            if envelope_type not in CODEX_SESSION_TOP_LEVEL_EVENTS:
                unknown.append(f"session.jsonl:{event['_line']}:unknown top-level event {envelope_type!r}")
                continue
            if envelope_type not in {"response_item", "event_msg"}:
                continue
            payload = event.get("payload")
            if not isinstance(payload, dict):
                unknown.append(f"session.jsonl:{event['_line']}:malformed {envelope_type} payload")
                continue
            payload_type = payload.get("type")
            if envelope_type == "event_msg":
                if payload_type in PASSIVE_CODEX_EVENT_MESSAGES:
                    continue
                if payload_type == "item_completed":
                    item = payload.get("item")
                    if not isinstance(item, dict):
                        unknown.append(
                            f"session.jsonl:{event['_line']}:malformed completed item"
                        )
                        continue
                    item_type = item.get("type")
                    if item_type in PASSIVE_CODEX_COMPLETED_ITEMS:
                        continue
                    normalized_type = ACTIVE_CODEX_COMPLETED_ITEMS.get(str(item_type))
                    if normalized_type is None:
                        unknown.append(
                            f"session.jsonl:{event['_line']}:unknown completed item type {item_type!r}"
                        )
                        continue
                    event_id = str(item.get("id") or f"session-line-{event['_line']}")
                    calls[event_id] = {
                        "event_id": event_id,
                        "source": "session.jsonl",
                        "line": event["_line"],
                        "name": _event_name_from_input(item),
                        "event_type": normalized_type,
                        "arguments": _call_arguments(
                            item.get("arguments")
                            if item.get("arguments") is not None
                            else item.get("input")
                            if item.get("input") is not None
                            else item.get("command")
                            if item.get("command") is not None
                            else item.get("changes")
                        ),
                    }
                    continue
                if payload_type not in ACTIVE_CODEX_EVENT_MESSAGES:
                    unknown.append(
                        f"session.jsonl:{event['_line']}:unknown event message type {payload_type!r}"
                    )
                    continue
            elif payload_type in CODEX_SESSION_RESULT_TYPES:
                event_id = str(
                    payload.get("call_id") or payload.get("id") or f"session-line-{event['_line']}"
                )
                if event_id not in calls:
                    calls[event_id] = {
                        "event_id": event_id,
                        "source": "session.jsonl",
                        "line": event["_line"],
                        "name": "observed_tool_result_without_call",
                        "event_type": str(payload_type),
                        "arguments": None,
                    }
                continue
            elif payload_type in PASSIVE_SESSION_RESPONSE_TYPES:
                continue
            elif payload_type not in CALL_SESSION_TYPES:
                unknown.append(
                    f"session.jsonl:{event['_line']}:unknown response item type {payload_type!r}"
                )
                continue
            event_id = str(payload.get("call_id") or payload.get("id") or f"session-line-{event['_line']}")
            if event_id not in calls:
                calls[event_id] = {
                    "event_id": event_id,
                    "source": "session.jsonl",
                    "line": event["_line"],
                    "name": str(payload.get("name") or payload_type),
                    "event_type": str(payload_type),
                    "arguments": _call_arguments(
                        payload.get("arguments")
                        if payload.get("arguments") is not None
                        else payload.get("input")
                    ),
                }
    elif driver == "kimi":
        for event in events:
            role = event.get("role")
            event_type = event.get("type")
            if role is None:
                if event_type not in KIMI_TRANSCRIPT_TYPES:
                    unknown.append(f"transcript.jsonl:{event['_line']}:unknown top-level event {event_type!r}")
                continue
            if role not in KIMI_TRANSCRIPT_ROLES:
                unknown.append(f"transcript.jsonl:{event['_line']}:unknown message role {role!r}")
                continue
            if role == "tool":
                event_id = str(
                    event.get("tool_call_id") or event.get("id") or f"line-{event['_line']}-tool-result"
                )
                if event_id not in calls:
                    calls[event_id] = {
                        "event_id": event_id,
                        "source": "transcript.jsonl",
                        "line": event["_line"],
                        "name": "observed_tool_result_without_call",
                        "event_type": "tool_result",
                        "arguments": None,
                    }
                continue
            if role != "assistant":
                continue
            tool_calls = event.get("tool_calls") or []
            if not isinstance(tool_calls, list):
                unknown.append(f"transcript.jsonl:{event['_line']}:malformed tool_calls collection")
                continue
            for index, call in enumerate(tool_calls):
                if not isinstance(call, dict):
                    unknown.append(f"transcript.jsonl:{event['_line']}:malformed tool call")
                    continue
                function = call.get("function")
                if not isinstance(function, dict):
                    unknown.append(f"transcript.jsonl:{event['_line']}:malformed tool function")
                    continue
                event_id = str(call.get("id") or f"line-{event['_line']}-call-{index}")
                calls[event_id] = {
                    "event_id": event_id,
                    "source": "transcript.jsonl",
                    "line": event["_line"],
                    "name": str(function.get("name") or call.get("type") or "unknown_tool"),
                    "event_type": str(call.get("type") or "tool_call"),
                    "arguments": _call_arguments(function.get("arguments")),
                }
        wire_path = run_dir / "wire.jsonl"
        wire_events, wire_bad = iter_jsonl(wire_path) if wire_path.is_file() else ([], [])
        unknown.extend(f"wire.jsonl:{line}:malformed" for line in wire_bad)
        for event in wire_events:
            envelope_type = event.get("type")
            if envelope_type in KIMI_WIRE_PASSIVE_TYPES:
                continue
            if envelope_type != "context.append_loop_event":
                unknown.append(f"wire.jsonl:{event['_line']}:unknown top-level event {envelope_type!r}")
                continue
            loop_event = event.get("event")
            if not isinstance(loop_event, dict):
                unknown.append(f"wire.jsonl:{event['_line']}:malformed loop event")
                continue
            loop_type = loop_event.get("type")
            if loop_type == "content.part":
                part = loop_event.get("part")
                if not isinstance(part, dict) or part.get("type") not in {"text", "think"}:
                    unknown.append(
                        f"wire.jsonl:{event['_line']}:unknown or malformed content part {part.get('type') if isinstance(part, dict) else None!r}"
                    )
                continue
            if loop_type == "tool.result":
                event_id = str(
                    loop_event.get("toolCallId")
                    or loop_event.get("uuid")
                    or f"wire-line-{event['_line']}-tool-result"
                )
                if event_id not in calls:
                    calls[event_id] = {
                        "event_id": event_id,
                        "source": "wire.jsonl",
                        "line": event["_line"],
                        "name": "observed_tool_result_without_call",
                        "event_type": "tool.result",
                        "arguments": None,
                    }
                continue
            if loop_type in KIMI_WIRE_LOOP_PASSIVE_TYPES:
                continue
            if loop_type not in {"tool.call", "tool.call.delta", "tool.call.started"}:
                unknown.append(f"wire.jsonl:{event['_line']}:unknown loop event type {loop_type!r}")
                continue
            event_id = str(loop_event.get("toolCallId") or loop_event.get("uuid") or f"wire-line-{event['_line']}")
            if event_id not in calls:
                calls[event_id] = {
                    "event_id": event_id,
                    "source": "wire.jsonl",
                    "line": event["_line"],
                    "name": str(loop_event.get("name") or "tool.call"),
                    "event_type": str(loop_type),
                    "arguments": _call_arguments(
                        loop_event.get("arguments")
                        if loop_event.get("arguments") is not None
                        else loop_event.get("input")
                    ),
                }
    else:
        raise ValueError(f"unknown driver: {driver}")
    return sorted(calls.values(), key=lambda item: (item["source"], item["line"], item["event_id"])), unknown


def classify_calls(calls: list[dict[str, Any]], workspace_changed: bool) -> dict[str, bool]:
    names = [call["name"].lower() for call in calls]
    types = [call["event_type"].lower() for call in calls]
    arguments = []
    for call in calls:
        value = call.get("arguments")
        if isinstance(value, str):
            arguments.append(value.lower())
        elif isinstance(value, list) and all(isinstance(part, str) for part in value):
            arguments.append(" ".join(value).lower())
        else:
            arguments.append(json.dumps(value, sort_keys=True, ensure_ascii=False).lower())
    surfaces = [" ".join(parts) for parts in zip(names, types, arguments)]
    spawned = any(
        name in {"task", "agent", "agentswarm", "spawn_agent", "collaboration.spawn_agent"}
        or "spawn_agent" in name
        or "agent_swarm" in name
        or event_type in {"collab_agent_tool_call"}
        or "spawn_agent" in surface
        or "collaboration.spawn_agent" in surface
        for name, event_type, surface in zip(names, types, surfaces)
    )
    inspected = any(
        name in {"read", "grep", "glob", "imageview", "view_image", "read_file", "search_files"}
        or any(token in surface for token in (
            "tools.view_image", "tools.read", "tools.exec_command", " read ", " cat ", " sed -n", " head ",
            " tail ", " grep ", " rg ", " find ", " ls ", " pwd", "git status", "git diff",
            "open(", ".read_text(", ".read_bytes(", "os.listdir(", "os.scandir(", "glob.glob(",
            "/proc/",
        ))
        for name, surface in zip(names, surfaces)
    )
    researched = any(
        any(token in surface for token in (
            "websearch", "web_search", "webfetch", "web__run", "web.run", "fetchurl", "fetch_url",
            "research", "curl ", "wget ", "http://", "https://", "socket.", "requests.",
            "urllib.", "http.client", "httpx.", "aiohttp", "dns.resolver",
        ))
        for surface in surfaces
    )
    mutated = workspace_changed or any(
        name in {"write", "edit", "apply_patch", "file_change", "write_file", "create_file", "delete_file"}
        or event_type == "file_change"
        or any(token in surface for token in (
            "apply_patch", "tools.apply_patch", " sed -i", " tee ", "touch ", "mkdir ", "rm ", "mv ",
            "cp ", "git commit", "npm install", "pip install", " > ", ">>", ".write_text(",
            ".write_bytes(", "os.remove(", "os.unlink(", "os.rename(", "os.replace(", "shutil.move(",
        ))
        or bool(re.search(r"open\s*\([^)]*,\s*\\?[\"'][wax+]", surface))
        for name, event_type, surface in zip(names, types, surfaces)
    )
    unclassified = bool(calls) and not any((spawned, inspected, researched, mutated))
    return {
        "target_originated_tool_or_function_call": bool(calls),
        "spawned_agent": spawned,
        "repository_or_file_inspection": inspected,
        "research_or_network_action": researched,
        "implementation_or_mutation_attempt": mutated,
        "unclassified_tool_action": unclassified,
    }


def instruction_context(driver: str, events: list[dict[str, Any]], run_dir: Path) -> tuple[dict[str, Any], list[str]]:
    issues: list[str] = []
    if driver == "claude":
        init = next((event for event in events if event.get("type") == "system" and event.get("subtype") == "init"), None)
        if init is None:
            issues.append("missing Claude init event")
            return {"driver": driver, "native_system_text": "not exposed by stream-json", "init_event": None}, issues
        clean = {key: value for key, value in init.items() if key != "_line"}
        return {
            "driver": driver,
            "native_system_text": "not exposed by stream-json",
            "init_event": clean,
            "limitations": ["Claude Code does not expose the full native system/developer prompt in this artifact format."],
        }, issues
    if driver == "codex":
        session_path = run_dir / "session.jsonl"
        session, malformed = iter_jsonl(session_path)
        if malformed:
            issues.append(f"malformed Codex session lines: {malformed}")
        if not session:
            issues.append("missing Codex session rollout")
        base = None
        messages: list[dict[str, Any]] = []
        response_model_records: list[dict[str, Any]] = []
        turn_contexts: list[dict[str, Any]] = []
        world_states: list[dict[str, Any]] = []
        for event in session:
            payload = event.get("payload") or {}
            if event.get("type") == "session_meta":
                base = payload.get("base_instructions")
            elif event.get("type") == "response_item" and payload.get("type") == "message" and payload.get("role") in {"system", "developer", "user"}:
                messages.append({key: value for key, value in payload.items()})
            elif (
                event.get("type") == "response_item"
                and payload.get("type") == "message"
                and payload.get("role") == "assistant"
            ):
                record = {
                    key: payload.get(key)
                    for key in ("model", "model_id", "provider")
                    if key in payload
                }
                if record:
                    response_model_records.append(record)
            elif event.get("type") == "turn_context":
                turn_contexts.append(payload)
            elif event.get("type") == "world_state":
                world_states.append(payload)
        if base is None:
            issues.append("Codex base instructions missing from session rollout")
        return {
            "driver": driver,
            "base_instructions": base,
            "pre_response_messages": messages,
            "response_model_records": response_model_records,
            "turn_contexts": turn_contexts,
            "world_states": world_states,
            "limitations": ["API-served model identity and the complete native tool schema are not independently exposed."],
        }, issues
    if driver == "kimi":
        wire_path = run_dir / "wire.jsonl"
        wire, malformed = iter_jsonl(wire_path)
        if malformed:
            issues.append(f"malformed Kimi wire lines: {malformed}")
        if not wire:
            issues.append("missing Kimi wire journal")
        config = []
        active_tools = []
        tool_snapshots = []
        requests = []
        responses = []
        for event in wire:
            clean = {key: value for key, value in event.items() if key != "_line"}
            if event.get("type") == "config.update":
                config.append(clean)
            elif event.get("type") == "tools.set_active_tools":
                active_tools.append(clean)
            elif event.get("type") == "llm.tools_snapshot":
                tool_snapshots.append(clean)
            elif event.get("type") == "llm.request":
                requests.append(
                    {
                        key: clean.get(key)
                        for key in (
                            "type",
                            "time",
                            "maxTokens",
                            "model",
                            "modelAlias",
                            "provider",
                            "systemPromptHash",
                            "thinkingEffort",
                            "thinkingKeep",
                            "toolSelect",
                            "toolsHash",
                        )
                        if key in clean
                    }
                )
            elif event.get("type") == "llm.response":
                responses.append(
                    {
                        key: clean.get(key)
                        for key in ("type", "time", "model", "modelAlias", "provider")
                        if key in clean
                    }
                )
        if not any("systemPrompt" in event for event in config):
            issues.append("Kimi system prompt missing from wire journal")
        return {
            "driver": driver,
            "config_updates": config,
            "active_tools": active_tools,
            "tool_snapshots": tool_snapshots,
            "requests": requests,
            "responses": responses,
        }, issues
    raise ValueError(f"unknown driver: {driver}")


def observed_model_and_effort(driver: str, events: list[dict[str, Any]], context: dict[str, Any]) -> dict[str, Any]:
    models: list[str] = []
    model_aliases: list[str] = []
    providers: list[str] = []
    evidence: list[dict[str, str]] = []
    effort: Any = None
    identity_kind = "served"
    if driver == "claude":
        init_model = (context.get("init_event") or {}).get("model")
        if isinstance(init_model, str) and init_model:
            models.append(init_model)
            evidence.append({"kind": "requested_init_tag", "value": init_model})
        for event in events:
            model = (event.get("message") or {}).get("model") if event.get("type") == "assistant" else None
            if isinstance(model, str):
                if model not in models:
                    models.append(model)
                evidence.append({"kind": "served_response_tag", "value": model})
        identity_kind = "requested_init_and_served_response_tags"
    elif driver == "codex":
        for turn in context.get("turn_contexts") or []:
            model = turn.get("model")
            if isinstance(model, str) and model not in models:
                models.append(model)
                evidence.append({"kind": "requested_turn_context", "value": model})
            settings = ((turn.get("collaboration_mode") or {}).get("settings") or {})
            if settings.get("reasoning_effort") is not None:
                effort = settings["reasoning_effort"]
        for event in events:
            item = event.get("item")
            model = item.get("model") if isinstance(item, dict) else None
            if isinstance(model, str):
                if model not in models:
                    models.append(model)
                evidence.append({"kind": "served_response_item_tag", "value": model})
        for response in context.get("response_model_records") or []:
            for key in ("model", "model_id"):
                model = response.get(key)
                if isinstance(model, str) and model:
                    if model not in models:
                        models.append(model)
                    evidence.append(
                        {"kind": f"served_session_response_{key}_tag", "value": model}
                    )
            provider = response.get("provider")
            if isinstance(provider, str) and provider:
                if provider not in providers:
                    providers.append(provider)
                evidence.append(
                    {"kind": "served_session_response_provider_tag", "value": provider}
                )
        identity_kind = "requested_turn_context_and_response_item_tags_when_exposed"
    elif driver == "kimi":
        for request in context.get("requests") or []:
            model = request.get("model")
            if isinstance(model, str) and model not in models:
                models.append(model)
                evidence.append({"kind": "request_wire_record", "value": model})
            alias = request.get("modelAlias")
            if isinstance(alias, str) and alias:
                if alias not in model_aliases:
                    model_aliases.append(alias)
                evidence.append({"kind": "request_wire_alias", "value": alias})
            provider = request.get("provider")
            if isinstance(provider, str) and provider:
                if provider not in providers:
                    providers.append(provider)
                evidence.append({"kind": "request_wire_provider", "value": provider})
            if request.get("thinkingEffort") is not None:
                effort = request["thinkingEffort"]
        for event in events:
            model = event.get("model") if event.get("role") == "assistant" else None
            if isinstance(model, str):
                if model not in models:
                    models.append(model)
                evidence.append({"kind": "served_assistant_tag", "value": model})
        for response in context.get("responses") or []:
            model = response.get("model")
            if isinstance(model, str):
                if model not in models:
                    models.append(model)
                evidence.append({"kind": "served_wire_response_tag", "value": model})
            alias = response.get("modelAlias")
            if isinstance(alias, str) and alias:
                if alias not in model_aliases:
                    model_aliases.append(alias)
                evidence.append({"kind": "served_wire_response_alias", "value": alias})
            provider = response.get("provider")
            if isinstance(provider, str) and provider:
                if provider not in providers:
                    providers.append(provider)
                evidence.append({"kind": "served_wire_response_provider", "value": provider})
        identity_kind = "request_wire_record_and_served_response_tags_when_exposed"
    return {
        "models": models,
        "model_aliases": model_aliases,
        "providers": providers,
        "model_evidence": evidence,
        "identity_kind": identity_kind,
        "observed_effort": effort,
    }


def _frozen_credential_structure_sha256(driver: str) -> str:
    lock = load_json(ROOT / CONFIG_LOCK_REL)
    matches = [
        value.get("redacted_credential_structure_sha256")
        for value in (lock.get("conditions") or {}).values()
        if isinstance(value, dict) and value.get("driver") == driver
    ]
    if len(matches) != 1 or not re.fullmatch(r"[0-9a-f]{64}", str(matches[0] or "")):
        raise ValueError(f"frozen credential structure is unavailable for {driver}")
    return str(matches[0])


def credential_receipt_issues(
    path: Path,
    driver: str,
    *,
    expected_source_structure_sha256: str | None = None,
) -> list[str]:
    """Validate only aggregate scanner evidence; never load or expect secret values."""
    if path.is_symlink() or not path.is_file():
        return [f"missing regular credential scan receipt: {path.name}"]
    try:
        receipt = load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"malformed credential scan receipt {path.name}: {type(exc).__name__}"]
    if not isinstance(receipt, dict):
        return [f"credential scan receipt is not an object: {path.name}"]
    errors = []
    if set(receipt) != CREDENTIAL_RECEIPT_FIELDS:
        errors.append(f"credential scan receipt fields differ from frozen schema: {path.name}")
    if receipt.get("schema_version") != 1 or receipt.get("driver") != driver:
        errors.append(f"credential scan receipt identity mismatch: {path.name}")
    try:
        expected_structure = expected_source_structure_sha256 or _frozen_credential_structure_sha256(driver)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"frozen credential structure unavailable: {type(exc).__name__}")
    else:
        if receipt.get("source_redacted_credential_structure_sha256") != expected_structure:
            errors.append(f"credential source schema drift: {path.name}")
    positive_counts = ("credential_pattern_count", "scanned_entry_count", "scanned_path_bytes")
    zero_counts = ("leak_match_count", "unsafe_special_entry_count", "escaping_symlink_count")
    if any(
        not isinstance(receipt.get(key), int)
        or isinstance(receipt.get(key), bool)
        or receipt[key] <= 0
        for key in positive_counts
    ):
        errors.append(f"credential scan receipt has invalid coverage: {path.name}")
    byte_count = receipt.get("scanned_regular_and_symlink_bytes")
    if not isinstance(byte_count, int) or isinstance(byte_count, bool) or byte_count < 0:
        errors.append(f"credential scan receipt has invalid byte count: {path.name}")
    if any(
        not isinstance(receipt.get(key), int)
        or isinstance(receipt.get(key), bool)
        or receipt[key] != 0
        for key in zero_counts
    ):
        errors.append(f"credential scan receipt reports unsafe content: {path.name}")
    if receipt.get("pass") is not True:
        errors.append(f"credential scan receipt did not pass: {path.name}")
    return errors


def _normalize_dynamic_policy_value(value: Any) -> Any:
    """Remove per-run scratch paths without weakening policy-content comparison."""
    if isinstance(value, dict):
        return {key: _normalize_dynamic_policy_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_dynamic_policy_value(item) for item in value]
    if isinstance(value, str):
        stage_prefix = r"(?:arena-plan-attempt\.[A-Za-z0-9_]+/runtime/)?"
        value = re.sub(rf"/tmp/{stage_prefix}arena-ws\.[A-Za-z0-9]+", "[workspace]", value)
        return re.sub(
            rf"/tmp/{stage_prefix}arena-(?:claude|codex|kimi)-home\.[A-Za-z0-9]+",
            "[auth-home]",
            value,
        )
    return value


def instruction_policy_signature(driver: str, context: dict[str, Any]) -> dict[str, Any]:
    if driver == "claude":
        init = context.get("init_event") or {}
        keys = (
            "agents",
            "capabilities",
            "claude_code_version",
            "mcp_servers",
            "model",
            "output_style",
            "permissionMode",
            "plugins",
            "skills",
            "tools",
        )
        value = {key: init.get(key) for key in keys}
    elif driver == "codex":
        contexts = context.get("turn_contexts") or []
        value = _normalize_dynamic_policy_value({
            "base_instructions": context.get("base_instructions"),
            "system_and_developer_messages": [
                message
                for message in context.get("pre_response_messages") or []
                if message.get("role") in {"system", "developer"}
            ],
            "turn_policy": {
                key: contexts[0].get(key)
                for key in (
                    "approval_policy",
                    "collaboration_mode",
                    "model",
                    "multi_agent_mode",
                    "permission_profile",
                    "personality",
                    "sandbox_policy",
                )
            }
            if contexts
            else None,
        })
    elif driver == "kimi":
        normalized_updates = []
        for item in context.get("config_updates") or []:
            normalized = {key: item.get(key) for key in item if key != "time"}
            if isinstance(normalized.get("systemPrompt"), str):
                text = normalized["systemPrompt"]
                text = re.sub(
                    r"The current date and time in ISO format is `[^`]*`",
                    "The current date and time in ISO format is `[dynamic]`",
                    text,
                )
                text = re.sub(
                    r"The current working directory is `[^`]*`",
                    "The current working directory is `[dynamic]`",
                    text,
                )
                normalized["systemPrompt"] = text
            normalized_updates.append(normalized)
        value = {
            "config_updates": normalized_updates,
            "active_tools": (context.get("active_tools") or [{}])[0].get("names"),
            "tool_snapshot": {
                key: (context.get("tool_snapshots") or [{}])[0].get(key) for key in ("hash", "tools")
            },
            "request": {
                key: (context.get("requests") or [{}])[0].get(key)
                for key in (
                    "maxTokens",
                    "model",
                    "modelAlias",
                    "provider",
                    "systemPromptHash",
                    "thinkingEffort",
                    "thinkingKeep",
                    "toolSelect",
                    "toolsHash",
                )
            },
        }
    else:
        raise ValueError(f"unknown driver: {driver}")
    return {"sha256": sha256_bytes(canonical_json(value)), "value": value}


def run_identifiers(driver: str, events: list[dict[str, Any]]) -> dict[str, list[str]]:
    identifiers: dict[str, list[str]] = defaultdict(list)
    if driver == "claude":
        for event in events:
            for key in ("session_id", "request_id"):
                value = event.get(key)
                if isinstance(value, str) and value not in identifiers[key]:
                    identifiers[key].append(value)
    elif driver == "codex":
        for event in events:
            if event.get("type") == "thread.started" and isinstance(event.get("thread_id"), str):
                identifiers["thread_id"].append(event["thread_id"])
    elif driver == "kimi":
        for event in events:
            if event.get("type") == "session.resume_hint" and isinstance(event.get("session_id"), str):
                identifiers["session_id"].append(event["session_id"])
    return dict(identifiers)


def artifact_records(run_dir: Path) -> list[dict[str, Any]]:
    excluded = {"artifact_manifest.json"}
    records = []
    for path in sorted(run_dir.rglob("*")):
        if path.parent == run_dir and path.name in excluded:
            continue
        metadata = path.lstat()
        base = {"path": str(path.relative_to(run_dir))}
        if stat.S_ISREG(metadata.st_mode):
            data = path.read_bytes()
            records.append({**base, "type": "regular_file", "sha256": sha256_bytes(data), "bytes": len(data)})
        elif stat.S_ISDIR(metadata.st_mode):
            records.append({**base, "type": "directory"})
        elif stat.S_ISLNK(metadata.st_mode):
            target = os.readlink(path).encode(errors="surrogateescape")
            records.append(
                {**base, "type": "symlink", "target_sha256": sha256_bytes(target), "target_bytes": len(target)}
            )
        else:
            raise ValueError(f"unsafe special filesystem entry in run artifacts: {base['path']}")
    return records


def completion_observation(
    driver: str, events: list[dict[str, Any]], metrics: dict[str, Any], output: str
) -> dict[str, Any]:
    """Normalize only structured completion facts exposed by the drivers."""
    exit_code = metrics.get("agent_exit")
    statuses: list[str] = []
    if driver == "claude":
        for event in events:
            if event.get("type") == "result":
                for key in ("subtype", "stop_reason"):
                    value = event.get(key)
                    if isinstance(value, str) and value not in statuses:
                        statuses.append(value)
    elif driver == "codex":
        statuses.extend(
            str(event.get("type"))
            for event in events
            if event.get("type") in {"turn.completed", "turn.failed", "error"}
        )
    elif driver == "kimi":
        statuses.extend(
            str(event.get("type"))
            for event in events
            if isinstance(event.get("type"), str) and event.get("type") in {"error", "result"}
        )
    status_text = " ".join(statuses).lower()
    explicitly_rejected_before_request = False
    request_acceptance_observed: bool | None = None
    pre_request_phases = {
        "before_request",
        "pre_request",
        "request_not_sent",
        "before_request_acceptance",
        "transport_before_request",
    }
    post_request_types = {
        "assistant",
        "result",
        "item.completed",
        "item.started",
        "item.updated",
        "turn.completed",
        "turn.failed",
        "turn.started",
    }
    target_response_activity_observed = False
    for event in events:
        accepted = event.get("request_accepted")
        if accepted is None:
            accepted = event.get("requestAccepted")
        phase = event.get("failure_phase")
        if phase is None:
            phase = event.get("failurePhase")
        normalized_phase = (
            str(phase).strip().lower().replace("-", "_")
            if phase is not None
            else ""
        )
        if accepted is True:
            request_acceptance_observed = True
        elif accepted is False and normalized_phase in pre_request_phases:
            explicitly_rejected_before_request = True
            if request_acceptance_observed is None:
                request_acceptance_observed = False
        if event.get("type") in post_request_types or event.get("role") == "assistant":
            request_acceptance_observed = True
        if driver == "claude" and event.get("type") == "assistant":
            target_response_activity_observed = True
        elif driver == "codex" and isinstance(event.get("item"), dict):
            target_response_activity_observed = True
        elif driver == "kimi" and event.get("role") == "assistant":
            target_response_activity_observed = True
    unavailable_metrics = [
        name
        for name in ("input_tokens", "output_tokens", "total_cost_usd")
        if metrics.get(name) is None
    ]
    return {
        "agent_exit": exit_code,
        "timeout_exit": exit_code == 124,
        "output_present": bool(output),
        "structured_statuses": statuses,
        "request_acceptance_observed": request_acceptance_observed,
        "pre_request_transport_failure_observed": explicitly_rejected_before_request
        and request_acceptance_observed is not True,
        "target_response_activity_observed": target_response_activity_observed,
        "truncation_observed": exit_code == 124
        or any(token in status_text for token in ("max_turn", "max_token", "length", "truncat")),
        "descriptive_metrics_unavailable": unavailable_metrics,
        "refusal_observed": None,
        "refusal_observability": "no cross-driver structured refusal field; semantic nonanswers remain in the output",
    }


def observe_run(
    manifest: dict[str, Any],
    slot: dict[str, Any],
    run_dir: Path,
    *,
    expected_policy_signature: str | None = None,
    finalize_artifact_manifest: bool = True,
) -> dict[str, Any]:
    condition = condition_map(manifest)[slot["condition_id"]]
    driver = condition["driver"]
    for name in OBSERVER_ARTIFACTS:
        path = run_dir / name
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"refusing target-created or preexisting derived artifact: {name}")
    peek = (run_dir / "peek_check").read_text(errors="replace") if (run_dir / "peek_check").is_file() else ""
    if "SECRET LEAK" in peek:
        raise SecretLeakError("driver secret scan marked this attempt for quarantine")
    events, malformed = iter_jsonl(run_dir / "transcript.jsonl")
    output, output_source = extract_final_output(driver, run_dir, events)
    (run_dir / "final_output.txt").write_text(output)
    calls, trace_unknown = detect_tool_events(driver, events, run_dir)
    workspace_changed = bool((run_dir / "workspace.diff").is_file() and (run_dir / "workspace.diff").stat().st_size)
    classifications = classify_calls(calls, workspace_changed)
    embargo = {
        "schema_version": 1,
        "slot_id": slot["slot_id"],
        "pass": not classifications["target_originated_tool_or_function_call"]
        and not workspace_changed
        and not trace_unknown,
        "trace_integrity_pass": not trace_unknown,
        "trace_integrity_failure": bool(trace_unknown),
        "workspace_changed": workspace_changed,
        "tool_call_count": len(calls),
        "tool_calls": calls,
        "trace_unknowns": trace_unknown,
        **classifications,
    }
    write_json(run_dir / "embargo.json", embargo)
    context, context_issues = instruction_context(driver, events, run_dir)
    write_json(run_dir / "instruction_context.json", context)
    observed = observed_model_and_effort(driver, events, context)
    identifiers = run_identifiers(driver, events)
    policy_signature = instruction_policy_signature(driver, context)
    metrics: dict[str, Any] = {}
    run_env: dict[str, Any] = {}
    for path, destination in ((run_dir / "metrics.json", metrics), (run_dir / "run_env.json", run_env)):
        if not path.is_file():
            continue
        try:
            parsed = load_json(path)
            if isinstance(parsed, dict):
                destination.update(parsed)
            else:
                context_issues.append(f"{path.name} is not a JSON object")
        except (OSError, json.JSONDecodeError) as exc:
            context_issues.append(f"malformed {path.name}: {exc}")
    required = COMMON_ARTIFACTS + RAW_ARTIFACTS[driver]
    missing = [
        name
        for name in required
        if (run_dir / name).is_symlink() or not (run_dir / name).is_file()
    ]
    technical_issues = [f"missing required artifact: {name}" for name in missing]
    for name in ("credential_scan.raw.json", "credential_scan.runtime.json"):
        technical_issues.extend(credential_receipt_issues(run_dir / name, driver))
    technical_issues.extend(f"malformed transcript line: {line}" for line in malformed)
    technical_issues.extend(f"unknown trace shape: {value}" for value in trace_unknown)
    technical_issues.extend(context_issues)
    identifier_key = {"claude": "session_id", "codex": "thread_id", "kimi": "session_id"}[driver]
    if len(identifiers.get(identifier_key) or []) != 1:
        technical_issues.append(f"expected exactly one emitted {identifier_key} for run association")
    for metric_name in ("input_tokens", "output_tokens", "total_cost_usd"):
        if metric_name not in metrics:
            technical_issues.append(f"missing descriptive metric field: {metric_name}")
            continue
        value = metrics.get(metric_name)
        if value is not None and (
            not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0
        ):
            technical_issues.append(f"invalid descriptive metric: {metric_name}")
    wall_seconds = metrics.get("wall_seconds")
    if (
        not isinstance(wall_seconds, (int, float))
        or isinstance(wall_seconds, bool)
        or wall_seconds < 0
    ):
        technical_issues.append("missing or invalid required descriptive metric: wall_seconds")
    if expected_policy_signature is not None and policy_signature["sha256"] != expected_policy_signature:
        technical_issues.append(
            f"instruction/tool policy drift: expected {expected_policy_signature}, got {policy_signature['sha256']}"
        )
    prompt_path = run_dir / "prompt.txt"
    prompt_sha = sha256_path(prompt_path) if prompt_path.is_file() else None
    if prompt_sha != manifest["task"]["prompt_sha256"]:
        technical_issues.append("delivered prompt hash mismatch")
    if run_env.get("prompt_sha256") != manifest["task"]["prompt_sha256"]:
        technical_issues.append("run environment prompt hash mismatch")
    frozen_prices = next(
        (item.get("sha256") for item in manifest.get("frozen_inputs") or [] if item.get("path") == "env/prices.json"),
        None,
    )
    if run_env.get("price_sheet_sha256") != frozen_prices:
        technical_issues.append("run environment price-sheet hash mismatch")
    if run_env.get("harness_tracked_dirty") is not False:
        technical_issues.append("harness had tracked changes at launch")
    cli_version = run_env.get("cli_version")
    if cli_version != condition.get("expected_cli_version"):
        technical_issues.append(f"CLI version drift: expected {condition.get('expected_cli_version')!r}, got {cli_version!r}")
    for field, expected_key in (
        ("base_url", "expected_base_url"),
        ("effort", "expected_effort_record"),
        ("setting_sources", "expected_setting_sources"),
    ):
        if run_env.get(field) != condition.get(expected_key):
            technical_issues.append(
                f"run environment {field} drift: expected {condition.get(expected_key)!r}, got {run_env.get(field)!r}"
            )
    if driver == "claude" and condition.get("model_env_expected") == "absent" and run_env.get("model_env") != "none":
        technical_issues.append("unexpected Claude model environment changed the frozen endpoint configuration")
    expected_models = set(condition.get("expected_model_identities") or [])
    if observed["models"] and any(model not in expected_models for model in observed["models"]):
        technical_issues.append(
            f"model mismatch: every observable identity must equal one of {sorted(expected_models)!r}, "
            f"observed {observed['models']!r}"
        )
    if not observed["models"]:
        technical_issues.append("observable model identity missing")
    expected_aliases = set(condition.get("expected_model_aliases") or [])
    if observed["model_aliases"] and any(
        alias not in expected_aliases for alias in observed["model_aliases"]
    ):
        technical_issues.append(
            f"model alias mismatch: expected only {sorted(expected_aliases)!r}, "
            f"observed {observed['model_aliases']!r}"
        )
    if expected_aliases and not observed["model_aliases"]:
        technical_issues.append("observable model alias missing")
    expected_providers = set(condition.get("expected_providers") or [])
    if observed["providers"] and any(
        provider not in expected_providers for provider in observed["providers"]
    ):
        technical_issues.append(
            f"provider mismatch: expected only {sorted(expected_providers)!r}, "
            f"observed {observed['providers']!r}"
        )
    if expected_providers and not observed["providers"]:
        technical_issues.append("observable provider missing")
    if driver == "kimi" and observed.get("observed_effort") != condition["effort"].get("observed_value"):
        technical_issues.append(
            f"effort drift: expected {condition['effort'].get('observed_value')!r}, got {observed.get('observed_effort')!r}"
        )
    output_bytes = output.encode()
    completion = completion_observation(driver, events, metrics, output)
    completion_notes = []
    agent_exit = metrics.get("agent_exit")
    if agent_exit not in {0, None}:
        completion_notes.append(f"agent process exit {agent_exit}; retain unless adjudicated exogenous")
    if not output:
        completion_notes.append("empty target output; retain as behavioral outcome unless caused by an exogenous pre-execution failure")
    if completion["descriptive_metrics_unavailable"]:
        completion_notes.append(
            "descriptive usage fields unavailable from emitted provider/CLI evidence: "
            + ", ".join(completion["descriptive_metrics_unavailable"])
        )
    state = "invalid_setup" if technical_issues else ("review_required" if completion_notes else "valid")
    record = {
        "schema_version": 1,
        "experiment_id": manifest["experiment_id"],
        "manifest_freeze_id": manifest["freeze_id"],
        "phase": manifest["phase"],
        "slot": slot,
        "condition": condition,
        "run_dir": relative(run_dir),
        "output": {
            "path": "final_output.txt",
            "source": output_source,
            "present": bool(output),
            "bytes": len(output_bytes),
            "sha256": sha256_bytes(output_bytes),
        },
        "configuration": {
            "run_env": run_env,
            "observed_identity": observed,
            "run_identifiers": identifiers,
            "instruction_policy_signature": policy_signature,
            "workspace_instruction_files": [
                relative(path)
                for name in ("AGENTS.md", "CLAUDE.md")
                for path in (ROOT / manifest["task"]["path"] / "fixture").rglob(name)
            ],
        },
        "metrics": metrics,
        "completion": completion,
        "embargo": embargo,
        "validity": {
            "state": state,
            "technical_issues": technical_issues,
            "completion_notes": completion_notes,
            "confirmatory_analysis_eligible": manifest["phase"] == "confirmatory" and not technical_issues,
            "smoke_excluded": manifest["phase"] == "smoke",
        },
        "observed_at": utc_now(),
    }
    exogenous_reasons = set(eligible_exclusion_reasons(record)) & {
        "external_termination_before_attributable_target_completion",
        "transport_or_service_failure_before_request_acceptance",
    }
    if exogenous_reasons:
        record["validity"]["state"] = "invalid_exogenous_pre_attribution"
        record["validity"]["confirmatory_analysis_eligible"] = False
        record["validity"]["exogenous_exclusion_evidence"] = sorted(exogenous_reasons)
    write_json(run_dir / "run_record.json", record)
    if finalize_artifact_manifest:
        write_artifact_manifest(manifest, slot, run_dir)
    return record


def write_artifact_manifest(
    manifest: dict[str, Any],
    slot: dict[str, Any],
    run_dir: Path,
    *,
    record_kind: str = "normalized_run",
) -> None:
    if record_kind not in {"normalized_run", "failed_attempt"}:
        raise ValueError(f"unsupported artifact manifest record kind: {record_kind}")
    path = run_dir / "artifact_manifest.json"
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite artifact manifest {path}")
    write_json(
        path,
        {
            "schema_version": 1,
            "slot_id": slot["slot_id"],
            "condition_id": slot["condition_id"],
            "driver": condition_map(manifest)[slot["condition_id"]]["driver"],
            "manifest_freeze_id": manifest["freeze_id"],
            "record_kind": record_kind,
            "artifacts": artifact_records(run_dir),
        },
    )


def verify_artifacts(run_dir: Path) -> list[str]:
    """Verify exact run-file coverage and the run-record identity anchor."""
    path = run_dir / "artifact_manifest.json"
    if not path.is_file():
        return ["artifact_manifest.json missing"]
    try:
        manifest = load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"artifact manifest unreadable: {exc}"]
    errors: list[str] = []
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        errors.append("artifact manifest has unsupported schema")
    record_kind = manifest.get("record_kind") if isinstance(manifest, dict) else None
    if record_kind not in {"normalized_run", "failed_attempt"}:
        errors.append("artifact manifest has unsupported record kind")
    records = manifest.get("artifacts") if isinstance(manifest, dict) else None
    if not isinstance(records, list):
        return errors + ["artifact manifest must contain an artifact inventory"]
    if record_kind == "normalized_run" and not records:
        errors.append("normalized artifact manifest must contain a nonempty inventory")
    indexed: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"artifact record {index} is not an object")
            continue
        name = record.get("path")
        relative_path = Path(name) if isinstance(name, str) else Path()
        if (
            not isinstance(name, str)
            or not name
            or relative_path.is_absolute()
            or ".." in relative_path.parts
        ):
            errors.append(f"artifact record {index} has an unsafe path")
            continue
        if name in indexed:
            errors.append(f"duplicate artifact record: {name}")
            continue
        indexed[name] = record
    actual: dict[str, str] = {}
    for item in run_dir.rglob("*"):
        if item.parent == run_dir and item.name == "artifact_manifest.json":
            continue
        mode = item.lstat().st_mode
        kind = (
            "regular_file"
            if stat.S_ISREG(mode)
            else "directory"
            if stat.S_ISDIR(mode)
            else "symlink"
            if stat.S_ISLNK(mode)
            else "special"
        )
        actual[str(item.relative_to(run_dir))] = kind
    if set(indexed) != set(actual):
        errors.append(
            f"artifact inventory differs from run directory: missing={sorted(set(actual) - set(indexed))}, "
            f"unlisted={sorted(set(indexed) - set(actual))}"
        )
    for name, record in indexed.items():
        artifact = run_dir / name
        if name not in actual:
            errors.append(f"artifact missing: {name}")
            continue
        if record.get("type") != actual[name]:
            errors.append(f"artifact type changed: {name}")
        elif actual[name] == "regular_file":
            if sha256_path(artifact) != record.get("sha256") or artifact.lstat().st_size != record.get("bytes"):
                errors.append(f"artifact changed: {name}")
        elif actual[name] == "symlink":
            target = os.readlink(artifact).encode(errors="surrogateescape")
            if sha256_bytes(target) != record.get("target_sha256") or len(target) != record.get("target_bytes"):
                errors.append(f"artifact symlink changed: {name}")
        elif actual[name] == "special":
            errors.append(f"unsafe special artifact entry: {name}")
    driver = manifest.get("driver") if isinstance(manifest, dict) else None
    condition_id = manifest.get("condition_id") if isinstance(manifest, dict) else None
    if driver not in RAW_ARTIFACTS:
        errors.append("artifact manifest has unknown driver")
    for name in (
        "credential_scan.raw.json",
        "credential_scan.runtime.json",
        "credential_scan.json",
    ):
        if name in actual and actual[name] == "regular_file" and driver in RAW_ARTIFACTS:
            errors.extend(credential_receipt_issues(run_dir / name, driver))
    if record_kind == "failed_attempt":
        if not isinstance(condition_id, str) or not condition_id:
            errors.append("failed-attempt artifact manifest lacks a condition ID")
        return errors
    run_record_path = run_dir / "run_record.json"
    if not run_record_path.is_file():
        return errors + ["run_record.json missing from artifact inventory"]
    try:
        run_record = load_json(run_record_path)
    except (OSError, json.JSONDecodeError) as exc:
        return errors + [f"run record unreadable: {exc}"]
    run_driver = ((run_record.get("condition") or {}).get("driver")) if isinstance(run_record, dict) else None
    if run_driver != driver:
        errors.append("artifact manifest driver does not match run record")
    if run_driver not in RAW_ARTIFACTS:
        errors.append("run record has unknown driver")
    else:
        required = set(COMMON_ARTIFACTS + RAW_ARTIFACTS[run_driver] + DERIVED_ARTIFACTS)
        missing_required = required - set(actual)
        if missing_required:
            errors.append(f"required artifacts absent: {sorted(missing_required)}")
        wrong_types = sorted(name for name in required & set(actual) if actual[name] != "regular_file")
        if wrong_types:
            errors.append(f"required artifacts are not regular files: {wrong_types}")
    slot_id = ((run_record.get("slot") or {}).get("slot_id")) if isinstance(run_record, dict) else None
    if manifest.get("slot_id") != slot_id:
        errors.append("artifact manifest slot_id does not match run record")
    if manifest.get("manifest_freeze_id") != run_record.get("manifest_freeze_id"):
        errors.append("artifact manifest freeze ID does not match run record")
    if manifest.get("condition_id") != ((run_record.get("slot") or {}).get("condition_id")):
        errors.append("artifact manifest condition_id does not match run record")
    return errors


def eligible_exclusion_reasons(record: dict[str, Any]) -> list[str]:
    issues = [str(value).lower() for value in (record.get("validity") or {}).get("technical_issues") or []]
    reasons: set[str] = set()
    if any("prompt" in issue and "mismatch" in issue for issue in issues):
        reasons.add("prompt_hash_mismatch")
    if any(token in issue for issue in issues for token in (
        "cli version drift", "model mismatch", "model alias mismatch", "provider mismatch",
        "effort drift", "run environment", "harness had tracked changes",
        "price-sheet hash mismatch", "frozen configuration", "instruction/tool policy drift",
    )):
        reasons.add("wrong_model_or_frozen_configuration")
    if any(token in issue for issue in issues for token in (
        "missing required artifact",
        "malformed",
        "base instructions missing",
        "init event",
        "session rollout",
        "system prompt missing",
        "observable model identity missing",
        "observable model alias missing",
        "observable provider missing",
    )):
        reasons.add("corrupted_or_missing_raw_artifact_due_to_harness")
    completion = record.get("completion") or {}
    embargo = record.get("embargo") or {}
    no_attributable_target_activity = (
        not (record.get("output") or {}).get("present")
        and not embargo.get("target_originated_tool_or_function_call")
        and not embargo.get("workspace_changed")
        and embargo.get("trace_integrity_pass") is True
        and completion.get("target_response_activity_observed") is not True
    )
    if (
        no_attributable_target_activity
        and completion.get("pre_request_transport_failure_observed") is True
    ):
        reasons.add("transport_or_service_failure_before_request_acceptance")
    exit_code = completion.get("agent_exit")
    if no_attributable_target_activity and exit_code in {130, 137, 143}:
        reasons.add("external_termination_before_attributable_target_completion")
    return sorted(reasons)


def validate_attempt_intents(
    manifest: dict[str, Any],
    ledger: list[dict[str, Any]],
    *,
    launch_slot_id: str | None = None,
    intent_state: tuple[dict[str, dict[str, Any]], list[str]] | None = None,
    claim_state: tuple[list[dict[str, Any]], list[str]] | None = None,
) -> list[str]:
    """Bind the journal, intent files, and ledger without forgiving gaps."""
    if not attempt_intent_enabled(manifest):
        return []
    records, intent_errors = (
        read_attempt_intents(manifest) if intent_state is None else intent_state
    )
    errors = list(intent_errors)
    claims, claim_errors = (
        read_attempt_claims(manifest) if claim_state is None else claim_state
    )
    errors.extend(claim_errors)
    claim_by_slot = {
        str(item["record"].get("slot_id")): item for item in claims
    }
    journal_enabled = attempt_claim_journal_enabled(manifest)
    all_slots = {
        slot["slot_id"]: slot
        for slot in [*(manifest.get("schedule") or []), *(manifest.get("reserve_slots") or [])]
    }
    ledger_by_slot = {
        str(row.get("slot_id")): row
        for row in ledger
        if isinstance(row, dict) and row.get("slot_id") in all_slots
    }
    for slot_id, row in ledger_by_slot.items():
        intent = records.get(slot_id)
        location = f"execution ledger row for {slot_id}"
        claim = claim_by_slot.get(slot_id)
        if journal_enabled:
            if claim is None:
                errors.append(f"{location} lacks its authoritative attempt-claim journal row")
            else:
                expected_claim_path = str(
                    Path(manifest["bout_dir"]) / ATTEMPT_CLAIM_JOURNAL
                )
                if row.get("attempt_claim_journal") != expected_claim_path:
                    errors.append(f"{location} attempt-claim journal path mismatch")
                if row.get("attempt_claim_sequence") != claim["line"]:
                    errors.append(f"{location} attempt-claim sequence mismatch")
                if row.get("attempt_claim_sha256") != claim["sha256"]:
                    errors.append(f"{location} attempt-claim hash mismatch")
        if intent is None:
            errors.append(f"{location} lacks its durable attempt intent")
            continue
        expected_path = str(
            Path(manifest["bout_dir"])
            / ATTEMPT_INTENT_DIRECTORY
            / f"{slot_id}.json"
        )
        if row.get("attempt_intent") != expected_path:
            errors.append(f"{location} attempt-intent path mismatch")
        if row.get("attempt_intent_sha256") != intent["sha256"]:
            errors.append(f"{location} attempt-intent hash mismatch")
        record = intent["record"]
        preflight = row.get("preflight") or {}
        for good, label in (
            (record.get("preflight_sha256") == preflight.get("sha256"), "preflight hash"),
            (record.get("harness_commit") == preflight.get("harness_commit"), "harness commit"),
            (record.get("replacement_for") == row.get("replacement_for"), "replacement parent"),
            (record.get("exclusion_reason") == row.get("exclusion_reason"), "exclusion reason"),
        ):
            if not good:
                errors.append(f"{location} and attempt intent have different {label}")
    if journal_enabled:
        journal_ids = [str(item["record"].get("slot_id")) for item in claims]
        ledger_ids = [
            str(row.get("slot_id"))
            for row in ledger
            if isinstance(row, dict) and row.get("slot_id") in all_slots
        ]
        if journal_ids[: len(ledger_ids)] != ledger_ids or len(ledger_ids) > len(
            journal_ids
        ):
            errors.append(
                "execution ledger order is not an exact prefix of the authoritative attempt-claim journal"
            )
        if len(journal_ids) > len(ledger_ids) + 1:
            errors.append(
                "multiple unresolved authoritative claims violate serial execution"
            )
        for slot_id, claim in claim_by_slot.items():
            intent = records.get(slot_id)
            if intent is None:
                errors.append(
                    f"authoritative attempt claim for {slot_id} lacks its durable attempt intent"
                )
                continue
            claim_record = claim["record"]
            intent_record = intent["record"]
            if claim_record.get("attempt_intent") != intent.get("path"):
                errors.append(
                    f"authoritative attempt claim for {slot_id} has a different intent path"
                )
            if claim_record.get("attempt_intent_sha256") != intent.get("sha256"):
                errors.append(
                    f"authoritative attempt claim for {slot_id} has a different intent hash"
                )
            for key in ATTEMPT_INTENT_FIELDS - {"record_kind"}:
                if claim_record.get(key) != intent_record.get(key):
                    errors.append(
                        f"authoritative attempt claim and intent for {slot_id} differ at {key}"
                    )
        for slot_id in sorted(set(records) - set(claim_by_slot)):
            errors.append(
                f"attempt intent for {slot_id} lacks its authoritative attempt-claim journal row"
            )
        authority_records = claim_by_slot
    else:
        authority_records = records
    primary_claims = [
        slot["slot_id"]
        for slot in manifest.get("schedule") or []
        if slot["slot_id"] in authority_records
    ]
    expected_primaries = [slot["slot_id"] for slot in manifest.get("schedule") or []]
    if set(primary_claims) != set(expected_primaries[: len(primary_claims)]):
        errors.append("attempt-intent primary claims are not a prefix of frozen sequence order")
    for condition_id in condition_map(manifest):
        reserve_claims = [
            slot["slot_id"]
            for slot in manifest.get("reserve_slots") or []
            if slot.get("condition_id") == condition_id
            and slot["slot_id"] in authority_records
        ]
        expected_reserves = [
            slot["slot_id"]
            for slot in manifest.get("reserve_slots") or []
            if slot.get("condition_id") == condition_id
        ]
        if set(reserve_claims) != set(expected_reserves[: len(reserve_claims)]):
            errors.append(
                f"attempt-intent reserve claims for {condition_id} are not in frozen reserve-index order"
            )
    allowed_reasons = set((manifest.get("exclusions") or {}).get("replace_only") or [])
    for slot_id, intent in authority_records.items():
        slot = all_slots.get(slot_id)
        if slot is None:
            continue
        record = intent["record"]
        if slot.get("kind") != "reserve":
            continue
        parent = ledger_by_slot.get(str(record.get("replacement_for")))
        reason = record.get("exclusion_reason")
        if parent is None:
            errors.append(f"attempt intent for {slot_id} lacks an earlier ledgered replacement parent")
        else:
            if parent.get("condition_id") != record.get("condition_id"):
                errors.append(f"attempt intent for {slot_id} has a cross-condition replacement parent")
            if parent.get("analysis_eligible") is not False:
                errors.append(f"attempt intent for {slot_id} may replace only an ineligible attempt")
            if reason not in set(parent.get("eligible_exclusion_reasons") or []):
                errors.append(f"attempt intent for {slot_id} has an unsupported exclusion reason")
        if reason not in allowed_reasons:
            errors.append(f"attempt intent for {slot_id} has a non-preregistered exclusion reason")
    unresolved = sorted(
        (set(records) | set(authority_records)) - set(ledger_by_slot)
    )
    if len(unresolved) > 1:
        errors.append("multiple unresolved attempt intents violate serial execution")
    for slot_id in unresolved:
        paired = slot_id in records and (
            not journal_enabled or slot_id in claim_by_slot
        )
        if launch_slot_id == slot_id and paired and unresolved == [slot_id]:
            continue
        errors.append(
            f"unresolved attempt intent/claim for {slot_id} blocks every subsequent execution without retry"
        )
    return errors


def validate_confirmatory_delivery_order(
    manifest: dict[str, Any], ledger: list[dict[str, Any]]
) -> list[str]:
    """Require each ineligible attempt to be resolved before later primaries."""
    if manifest.get("phase") != "confirmatory":
        return []
    errors: list[str] = []
    pending: dict[str, Any] | None = None
    for index, row in enumerate(ledger, start=1):
        if not isinstance(row, dict):
            continue
        if pending is not None:
            if row.get("kind") != "reserve" or row.get(
                "replacement_for"
            ) != pending.get("slot_id"):
                errors.append(
                    f"execution ledger row {index} bypasses analysis-ineligible attempt {pending.get('slot_id')}; its next frozen reserve was required first"
                )
                continue
        elif row.get("kind") == "reserve":
            errors.append(
                f"execution ledger row {index} is a reserve without a current confirmatory pause"
            )
        pending = row if row.get("analysis_eligible") is False else None
    return errors


def authorize_attempt_launch(
    manifest: dict[str, Any],
    slot: dict[str, Any],
    ledger: list[dict[str, Any]],
    ledger_snapshot: dict[str, Any],
) -> dict[str, Any] | None:
    """Authorize from one fresh three-witness view immediately before launch."""
    ledger_path = ROOT / str(manifest.get("bout_dir", "")) / "EXECUTION.jsonl"
    fresh_ledger, fresh_snapshot = read_execution_ledger(ledger_path)
    if fresh_ledger != ledger or fresh_snapshot != ledger_snapshot:
        raise ValueError(
            "execution ledger changed after the attempt's prior-state validation"
        )
    if attempt_claim_journal_enabled(manifest):
        # Read the claim before its bound intent. A claim carries the immutable
        # intent hash, so a concurrent intent mutation cannot be hidden behind
        # a cached intent paired with a later journal read.
        claims, claim_errors = read_attempt_claims(manifest)
        intents, intent_errors = read_attempt_intents(manifest)
        claim_state = (claims, claim_errors)
        intent_state = (intents, intent_errors)
    else:
        claims = []
        claim_state = None
        intent_state = None
    final_ledger, final_snapshot = read_execution_ledger(ledger_path)
    if final_ledger != fresh_ledger or final_snapshot != fresh_snapshot:
        raise ValueError(
            "execution ledger changed during process-launch authorization"
        )
    errors = validate_execution_ledger(
        manifest,
        final_ledger,
        launch_slot_id=str(slot["slot_id"]),
        intent_state=intent_state,
        claim_state=claim_state,
    )
    errors.extend(
        # The current slot is already represented by its durable claim. The
        # pre-claim gate uses next_slot; the authorization gate validates the
        # complete claimed union without counting that same slot a second time.
        validate_smoke_call_budget(manifest, final_ledger)
    )
    if errors:
        raise ValueError(
            "attempt claim is not authorized for process launch:\n- "
            + "\n- ".join(errors)
        )
    if not attempt_claim_journal_enabled(manifest):
        return None
    matches = [
        item
        for item in claims
        if item["record"].get("slot_id") == slot["slot_id"]
    ]
    if len(matches) != 1 or matches[0]["line"] != len(final_ledger) + 1:
        raise ValueError(
            "the launch slot is not the sole next authoritative attempt claim"
        )
    return matches[0]


def validate_execution_ledger(
    manifest: dict[str, Any],
    ledger: list[dict[str, Any]],
    *,
    launch_slot_id: str | None = None,
    intent_state: tuple[dict[str, dict[str, Any]], list[str]] | None = None,
    claim_state: tuple[list[dict[str, Any]], list[str]] | None = None,
) -> list[str]:
    errors: list[str] = []
    all_slots = {
        slot["slot_id"]: slot for slot in [*(manifest.get("schedule") or []), *(manifest.get("reserve_slots") or [])]
    }
    seen: dict[str, dict[str, Any]] = {}
    child_by_parent: dict[str, str] = {}
    allowed_reasons = set((manifest.get("exclusions") or {}).get("replace_only") or [])
    for index, row in enumerate(ledger):
        location = f"execution ledger row {index + 1}"
        if not isinstance(row, dict):
            errors.append(f"{location} is not an object")
            continue
        slot_id = row.get("slot_id")
        if slot_id in seen:
            errors.append(f"{location} duplicates slot_id {slot_id}")
            continue
        slot = all_slots.get(slot_id)
        if slot is None:
            errors.append(f"{location} references non-frozen slot {slot_id}")
            continue
        seen[str(slot_id)] = row
        if row.get("phase") != manifest.get("phase"):
            errors.append(f"{location} phase does not match manifest")
        if row.get("condition_id") != slot.get("condition_id"):
            errors.append(f"{location} condition does not match frozen slot")
        if row.get("kind") != slot.get("kind", "primary"):
            errors.append(f"{location} kind does not match frozen slot")
        try:
            expected_dir = relative(output_dir_for(manifest, slot))
        except (KeyError, ValueError):
            expected_dir = None
        if row.get("run_dir") != expected_dir:
            errors.append(f"{location} run directory does not match frozen slot")
        if not isinstance(row.get("analysis_eligible"), bool):
            errors.append(f"{location} analysis_eligible must be boolean")
        if not isinstance(row.get("process_group_cleaned"), bool):
            errors.append(f"{location} process_group_cleaned must be boolean")
        if not isinstance(row.get("staged_attempt_retained"), bool):
            errors.append(f"{location} staged_attempt_retained must be boolean")
        if row.get("staged_attempt_retained") is True:
            raw_stage_path = row.get("staged_attempt_path")
            if not isinstance(raw_stage_path, str) or not raw_stage_path:
                errors.append(f"{location} retained stage lacks its external path")
            else:
                try:
                    stage_path = Path(raw_stage_path).resolve(strict=True)
                    stage_path.relative_to(ROOT.resolve())
                except (OSError, RuntimeError):
                    errors.append(f"{location} retained stage path is missing")
                except ValueError:
                    if Path(raw_stage_path).is_symlink() or not stage_path.is_dir():
                        errors.append(f"{location} retained stage path is not a real directory")
                else:
                    errors.append(f"{location} retained stage path must be outside the repository")
        elif row.get("staged_attempt_retained") is False and row.get(
            "staged_attempt_path"
        ) is not None:
            errors.append(f"{location} non-retained stage must not record a path")
        if row.get("artifact_manifest_sha256") is not None and not re.fullmatch(
            r"[0-9a-f]{64}", str(row.get("artifact_manifest_sha256") or "")
        ):
            errors.append(f"{location} artifact manifest lacks a valid hash anchor")
        if row.get("analysis_eligible") is True and not re.fullmatch(
            r"[0-9a-f]{64}", str(row.get("artifact_manifest_sha256") or "")
        ):
            errors.append(f"{location} eligible attempt lacks an artifact-manifest hash anchor")
        if row.get("analysis_eligible") is True and not re.fullmatch(
            r"[0-9a-f]{64}", str(row.get("instruction_policy_signature_sha256") or "")
        ):
            errors.append(f"{location} eligible attempt lacks an instruction/tool policy signature")
        for path_key, hash_key in (
            ("failure_receipt", "failure_receipt_sha256"),
            ("quarantine_receipt", "quarantine_receipt_sha256"),
            ("quarantine_failure_receipt", "quarantine_failure_receipt_sha256"),
            ("stage_quarantine_receipt", "stage_quarantine_receipt_sha256"),
        ):
            if row.get(path_key) is not None and not re.fullmatch(
                r"[0-9a-f]{64}", str(row.get(hash_key) or "")
            ):
                errors.append(f"{location} {path_key} lacks a content hash anchor")
        if (
            row.get("quarantine_receipt") is not None
            or row.get("quarantine_failure_receipt") is not None
            or row.get("stage_quarantine_receipt") is not None
        ) and row.get("failure_receipt") is None:
            errors.append(f"{location} quarantine evidence lacks an attempt-failure receipt")
        preflight = row.get("preflight")
        if not isinstance(preflight, dict):
            errors.append(f"{location} lacks a treatment preflight record")
        elif preflight.get("sha256") != sha256_bytes(
            canonical_json({key: value for key, value in preflight.items() if key != "sha256"})
        ):
            errors.append(f"{location} treatment-preflight hash is invalid")
        elif preflight.get("condition_id") != row.get("condition_id"):
            errors.append(f"{location} treatment preflight belongs to a different condition")
        expected_smoke = manifest.get("phase") == "smoke"
        if row.get("smoke_excluded") is not expected_smoke:
            errors.append(f"{location} smoke exclusion flag is inconsistent")
        replacement_for = row.get("replacement_for")
        if slot.get("kind") == "primary":
            if replacement_for is not None:
                errors.append(f"{location} primary slot cannot replace another attempt")
        else:
            parent = seen.get(str(replacement_for))
            if parent is None:
                errors.append(f"{location} reserve must link to an earlier attempted slot")
            else:
                if parent.get("condition_id") != row.get("condition_id"):
                    errors.append(f"{location} reserve and replaced attempt have different conditions")
                if parent.get("analysis_eligible") is not False:
                    errors.append(f"{location} may replace only an objectively ineligible attempt")
                reason = row.get("exclusion_reason")
                if reason not in allowed_reasons:
                    errors.append(f"{location} uses a non-preregistered exclusion reason")
                if reason not in set(parent.get("eligible_exclusion_reasons") or []):
                    errors.append(f"{location} exclusion reason is unsupported by the replaced attempt evidence")
            if replacement_for in child_by_parent:
                errors.append(f"{location} creates a second replacement for {replacement_for}")
            elif isinstance(replacement_for, str):
                child_by_parent[replacement_for] = str(slot_id)
    primary_order = [
        row.get("slot_id")
        for row in ledger
        if isinstance(row, dict) and row.get("kind") == "primary"
    ]
    expected_primary_order = [slot["slot_id"] for slot in manifest.get("schedule") or []]
    if primary_order != expected_primary_order[: len(primary_order)]:
        errors.append("execution ledger primary attempts are not a prefix of frozen sequence order")
    for condition_id in condition_map(manifest):
        attempted_reserves = [
            row.get("slot_id")
            for row in ledger
            if isinstance(row, dict)
            and row.get("kind") == "reserve"
            and row.get("condition_id") == condition_id
        ]
        expected_reserves = [
            slot["slot_id"]
            for slot in manifest.get("reserve_slots") or []
            if slot.get("condition_id") == condition_id
        ]
        if attempted_reserves != expected_reserves[: len(attempted_reserves)]:
            errors.append(f"reserve attempts for {condition_id} are not in frozen reserve-index order")
    errors.extend(validate_confirmatory_delivery_order(manifest, ledger))
    errors.extend(
        validate_attempt_intents(
            manifest,
            ledger,
            launch_slot_id=launch_slot_id,
            intent_state=intent_state,
            claim_state=claim_state,
        )
    )
    return errors


def select_effective_attempts(
    manifest: dict[str, Any], ledger: list[dict[str, Any]]
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors = validate_execution_ledger(manifest, ledger)
    by_slot = {row.get("slot_id"): row for row in ledger if isinstance(row, dict)}
    by_parent = {
        row.get("replacement_for"): row
        for row in ledger
        if isinstance(row, dict) and row.get("replacement_for") is not None
    }
    effective: dict[str, dict[str, Any]] = {}
    for primary in manifest.get("schedule") or []:
        row = by_slot.get(primary["slot_id"])
        visited: set[str] = set()
        while row is not None and row.get("analysis_eligible") is False:
            slot_id = str(row.get("slot_id"))
            if slot_id in visited:
                errors.append(f"replacement cycle for {primary['slot_id']}")
                row = None
                break
            visited.add(slot_id)
            row = by_parent.get(slot_id)
        if row is None:
            errors.append(f"no eligible attempt for primary slot {primary['slot_id']}")
        elif row.get("analysis_eligible") is not True:
            errors.append(f"effective attempt eligibility is invalid for {primary['slot_id']}")
        else:
            effective[primary["slot_id"]] = row
    return effective, errors


def validate_artifact_anchor(
    manifest: dict[str, Any], slot: dict[str, Any], ledger_row: dict[str, Any]
) -> tuple[Path | None, str | None, list[str]]:
    """Verify an exact retained run directory, including failed-attempt inventories."""
    errors: list[str] = []
    expected_dir = output_dir_for(manifest, slot)
    try:
        supplied_dir = (ROOT / str(ledger_row.get("run_dir", ""))).resolve()
        supplied_dir.relative_to(ROOT.resolve())
    except (OSError, ValueError):
        return None, None, [f"unsafe run directory for {slot['slot_id']}"]
    if supplied_dir != expected_dir.resolve():
        errors.append(f"run directory does not match frozen slot {slot['slot_id']}")
    artifact_manifest_path = supplied_dir / "artifact_manifest.json"
    expected_hash = ledger_row.get("artifact_manifest_sha256")
    if artifact_manifest_path.is_symlink() or not artifact_manifest_path.is_file():
        return supplied_dir, None, errors + [f"artifact manifest missing for {slot['slot_id']}"]
    if not re.fullmatch(r"[0-9a-f]{64}", str(expected_hash or "")):
        errors.append(f"{slot['slot_id']}: execution ledger lacks an artifact-manifest hash anchor")
    elif sha256_path(artifact_manifest_path) != expected_hash:
        errors.append(f"{slot['slot_id']}: artifact manifest does not match execution-ledger anchor")
    errors.extend(f"{slot['slot_id']}: {error}" for error in verify_artifacts(supplied_dir))
    try:
        artifact_manifest = load_json(artifact_manifest_path)
    except (OSError, json.JSONDecodeError) as exc:
        return supplied_dir, None, errors + [
            f"{slot['slot_id']}: artifact manifest unreadable: {exc}"
        ]
    record_kind = artifact_manifest.get("record_kind") if isinstance(artifact_manifest, dict) else None
    checks = (
        (artifact_manifest.get("slot_id") == slot.get("slot_id"), "slot ID"),
        (artifact_manifest.get("condition_id") == slot.get("condition_id"), "condition ID"),
        (artifact_manifest.get("manifest_freeze_id") == manifest.get("freeze_id"), "freeze ID"),
    )
    for good, label in checks:
        if not good:
            errors.append(f"{slot['slot_id']}: artifact-manifest {label} mismatch")
    return supplied_dir, record_kind, errors


def validate_run_provenance(
    manifest: dict[str, Any], slot: dict[str, Any], ledger_row: dict[str, Any]
) -> tuple[dict[str, Any] | None, list[str]]:
    supplied_dir, record_kind, errors = validate_artifact_anchor(manifest, slot, ledger_row)
    if supplied_dir is None:
        return None, errors
    if record_kind != "normalized_run":
        errors.append(f"{slot['slot_id']}: retained artifacts are not a normalized run")
    record_path = supplied_dir / "run_record.json"
    if not record_path.is_file():
        return None, errors + [f"run record missing for {slot['slot_id']}"]
    try:
        record = load_json(record_path)
    except (OSError, json.JSONDecodeError) as exc:
        return None, errors + [f"run record unreadable for {slot['slot_id']}: {exc}"]
    condition = condition_map(manifest).get(slot["condition_id"])
    checks = (
        (record.get("experiment_id") == manifest.get("experiment_id"), "experiment ID"),
        (record.get("manifest_freeze_id") == manifest.get("freeze_id"), "freeze ID"),
        (record.get("phase") == manifest.get("phase"), "phase"),
        ((record.get("slot") or {}).get("slot_id") == slot.get("slot_id"), "slot ID"),
        ((record.get("slot") or {}).get("condition_id") == slot.get("condition_id"), "slot condition"),
        (record.get("condition") == condition, "condition record"),
        (record.get("run_dir") == ledger_row.get("run_dir"), "run directory record"),
        ((record.get("validity") or {}).get("confirmatory_analysis_eligible") == ledger_row.get("analysis_eligible"), "eligibility"),
        ((record.get("validity") or {}).get("smoke_excluded") == ledger_row.get("smoke_excluded"), "smoke exclusion"),
        ((record.get("embargo") or {}).get("slot_id") == slot.get("slot_id"), "embargo slot"),
        (
            (record.get("configuration") or {}).get("run_env", {}).get("harness_commit")
            == (ledger_row.get("preflight") or {}).get("harness_commit"),
            "preflight harness commit",
        ),
        (
            (record.get("configuration") or {}).get("run_env", {}).get("cli_version")
            == (ledger_row.get("preflight") or {}).get("cli_version"),
            "preflight CLI version",
        ),
        (
            (record.get("configuration") or {}).get("instruction_policy_signature", {}).get("sha256")
            == ledger_row.get("instruction_policy_signature_sha256"),
            "instruction/tool policy signature",
        ),
    )
    for good, label in checks:
        if not good:
            errors.append(f"{slot['slot_id']}: run-record {label} mismatch")
    output_path = supplied_dir / "final_output.txt"
    if output_path.is_file():
        data = output_path.read_bytes()
        output = record.get("output") or {}
        if output.get("sha256") != sha256_bytes(data) or output.get("bytes") != len(data):
            errors.append(f"{slot['slot_id']}: final output does not match run record")
    return record, errors


def output_dir_for(manifest: dict[str, Any], slot: dict[str, Any]) -> Path:
    condition = condition_map(manifest)[slot["condition_id"]]
    return ROOT / manifest["bout_dir"] / Path(manifest["task"]["path"]).name / condition["output_label"] / f"run-{slot['replicate']}"


def driver_environment(driver: str, source: dict[str, str]) -> dict[str, str]:
    """Construct the exact minimal environment inherited by a driver process."""
    operational = {
        "HOME",
        "LANG",
        "LOGNAME",
        "PATH",
        "SHELL",
        "SSL_CERT_DIR",
        "SSL_CERT_FILE",
        "TERM",
        "TZ",
        "USER",
        "XDG_RUNTIME_DIR",
    }
    env = {
        key: value
        for key, value in source.items()
        if key in operational or key.startswith("LC_")
    }
    try:
        temp_metadata = SAFE_TEMP_ROOT.lstat()
        temp_root = SAFE_TEMP_ROOT.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"safe temp root is unavailable: {type(exc).__name__}") from exc
    if SAFE_TEMP_ROOT.is_symlink() or not stat.S_ISDIR(temp_metadata.st_mode):
        raise ValueError("safe temp root must be a real directory, not a symlink")
    if temp_root == ROOT or ROOT in temp_root.parents:
        raise ValueError("safe temp root must be outside the Agent Arena repository")
    if temp_root.stat().st_dev != ROOT.stat().st_dev:
        raise ValueError("safe temp root must share a filesystem with the repository for atomic transfer")
    env["TMPDIR"] = str(temp_root)
    source_name = {
        "claude": "ARENA_CLAUDE_HOME",
        "codex": "ARENA_CODEX_HOME",
        "kimi": "ARENA_KIMI_HOME",
    }[driver]
    if source.get(source_name):
        env[source_name] = source[source_name]
    env["ARENA_TIMEOUT_S"] = "600"
    env["ARENA_PLAN_PROBE"] = "1"
    if driver == "claude":
        for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL"):
            if source.get(name):
                env[name] = source[name]
        env["ARENA_EFFORT"] = "native-default"
        env["ARENA_SETTING_SOURCES"] = "project"
        env["ARENA_SETTING_SOURCES_RECORD"] = "project (fresh auth-only per-run home)"
    elif driver == "kimi":
        env["ARENA_KIMI_EFFORT"] = "native-default (observed in wire journal)"
    return env


def driver_command(manifest: dict[str, Any], slot: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    condition = condition_map(manifest)[slot["condition_id"]]
    driver = condition["driver"]
    script = {
        "claude": ROOT / "bin/run-task.sh",
        "codex": ROOT / "bin/run-task-codex.sh",
        "kimi": ROOT / "bin/run-task-kimi.sh",
    }[driver]
    command = [
        str(script),
        str(ROOT / manifest["task"]["path"]),
        condition["model_argument"],
        str(ROOT / manifest["bout_dir"]),
        str(slot["replicate"]),
    ]
    env = driver_environment(driver, dict(os.environ))
    if driver == "kimi":
        env["ARENA_KIMI_LABEL"] = condition["output_label"]
    return command, env


def prepare_staged_driver(
    manifest: dict[str, Any], slot: dict[str, Any], env: dict[str, str]
) -> tuple[Path, Path, list[str], dict[str, str]]:
    """Build a rubric-free live harness tree and external output path for one attempt."""
    condition = condition_map(manifest)[slot["condition_id"]]
    driver = condition["driver"]
    temp_base = Path(env["TMPDIR"]).resolve(strict=True)
    attempt_root = Path(tempfile.mkdtemp(prefix="arena-plan-attempt.", dir=temp_base))
    attempt_root.chmod(0o700)
    harness_root = attempt_root / "harness"
    runtime_root = attempt_root / "runtime"
    staged_bout = attempt_root / "bout"
    harness_root.mkdir(mode=0o700)
    runtime_root.mkdir(mode=0o700)
    staged_bout.mkdir(mode=0o700)
    try:
        for relative_path in STAGED_DRIVER_FILES[driver]:
            source = ROOT / relative_path
            if source.is_symlink() or not source.is_file():
                raise ValueError(f"staged driver input is not a regular file: {relative_path}")
            destination = harness_root / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            if sha256_path(source) != sha256_path(destination):
                raise ValueError(f"staged driver input hash mismatch: {relative_path}")
        source_task = ROOT / manifest["task"]["path"]
        staged_task = harness_root / manifest["task"]["path"]
        staged_task.mkdir(parents=True)
        shutil.copy2(source_task / "PROMPT.md", staged_task / "PROMPT.md")
        shutil.copytree(source_task / "fixture", staged_task / "fixture")
        staged_script = {
            "claude": harness_root / "bin/run-task.sh",
            "codex": harness_root / "bin/run-task-codex.sh",
            "kimi": harness_root / "bin/run-task-kimi.sh",
        }[driver]
        command = [
            str(staged_script),
            str(staged_task),
            condition["model_argument"],
            str(staged_bout),
            str(slot["replicate"]),
        ]
        staged_run_dir = (
            staged_bout
            / Path(manifest["task"]["path"]).name
            / condition["output_label"]
            / f"run-{slot['replicate']}"
        )
        staged_env = dict(env)
        staged_env["TMPDIR"] = str(runtime_root)
        staged_env["ARENA_PLAN_TMPDIR"] = str(runtime_root)
        return attempt_root, staged_run_dir, command, staged_env
    except BaseException:
        shutil.rmtree(attempt_root)
        raise


def recover_and_remove_staged_driver(attempt_root: Path, staged_run_dir: Path, run_dir: Path) -> None:
    """Atomically transfer a completed/partial run, then erase the exact external stage."""
    safe_base = SAFE_TEMP_ROOT.resolve(strict=True)
    resolved_attempt = attempt_root.resolve(strict=True)
    if resolved_attempt.parent != safe_base or not resolved_attempt.name.startswith("arena-plan-attempt."):
        raise ValueError("refusing unsafe staged-driver cleanup target")
    if staged_run_dir.exists() or staged_run_dir.is_symlink():
        if staged_run_dir.is_symlink() or not staged_run_dir.is_dir():
            raise ValueError("staged run output is not a real directory")
        if run_dir.exists() or run_dir.is_symlink():
            raise FileExistsError(f"refusing to overwrite recovered run directory {run_dir}")
        run_dir.parent.mkdir(parents=True, exist_ok=True)
        staged_run_dir.rename(run_dir)
    shutil.rmtree(resolved_attempt)


def _external_home(raw: str | None, label: str) -> tuple[Path | None, list[str]]:
    if not raw:
        return None, [f"{label} is not set"]
    unresolved = Path(raw).expanduser()
    path = unresolved.resolve()
    errors = []
    if unresolved.is_symlink():
        errors.append(f"{label} itself must not be a symlink")
    if not path.is_dir():
        errors.append(f"{label} is not an accessible directory")
    try:
        path.relative_to(ROOT.resolve())
    except ValueError:
        pass
    else:
        errors.append(f"{label} must be outside the Agent Arena repository")
    return path, errors


def preflight_condition(condition: dict[str, Any], env: dict[str, str]) -> tuple[dict[str, Any], list[str]]:
    """Check treatment-defining local state without invoking a target model."""
    driver = condition["driver"]
    errors: list[str] = []
    if driver == "claude":
        version_command = ["claude", "--version"]
    elif driver == "codex":
        version_command = ["codex", "--version"]
    else:
        version_command = [str(Path(env.get("HOME", str(Path.home()))) / ".kimi-code/bin/kimi"), "-V"]
    try:
        completed = subprocess.run(version_command, text=True, capture_output=True, check=False, timeout=30)
        raw_version = (completed.stdout or completed.stderr).splitlines()[0].strip() if (completed.stdout or completed.stderr) else ""
    except (OSError, subprocess.SubprocessError) as exc:
        raw_version = ""
        errors.append(f"could not query {driver} CLI version: {type(exc).__name__}")
    version = f"kimi-code {raw_version}" if driver == "kimi" and raw_version and not raw_version.startswith("kimi-code ") else raw_version
    if version != condition["expected_cli_version"]:
        errors.append(f"CLI version drift for {condition['condition_id']}: expected {condition['expected_cli_version']!r}, got {version!r}")

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=False
    ).stdout.strip()
    try:
        process_containment = process_scope_capability()
    except (OSError, RuntimeError, ValueError) as exc:
        process_containment = "unavailable"
        errors.append(f"process containment unavailable: {type(exc).__name__}")
    snapshot: dict[str, Any] = {
        "condition_id": condition["condition_id"],
        "driver": driver,
        "cli_version": version,
        "harness_commit": commit or "unknown",
        "environment_policy": "minimal-allowlist-v3",
        "execution_isolation_policy": "rubric-free staged driver; nondumpable parent; atomic output transfer; dedicated cgroup-v2 plus child subreaper",
        "process_containment": process_containment,
        "temp_root": env.get("TMPDIR"),
    }
    if driver == "claude":
        snapshot["credential_environment_fields_present"] = sorted(
            name for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN") if env.get(name)
        )
        home, home_errors = _external_home(env.get("ARENA_CLAUDE_HOME"), "ARENA_CLAUDE_HOME")
        errors.extend(home_errors)
        if home is not None:
            try:
                inventory, _ = credential_guard.inspect_source(driver, home)
                snapshot.update(
                    {
                        "credential_source_schema": inventory["source_schema"],
                        "credential_secret_field_count": inventory["secret_field_count"],
                        "redacted_credential_structure_sha256": inventory[
                            "redacted_credential_structure_sha256"
                        ],
                        "redacted_home_inventory_sha256": inventory[
                            "redacted_structural_inventory_sha256"
                        ],
                    }
                )
            except credential_guard.CredentialGuardError as exc:
                errors.append(f"Claude credential source invalid: {exc}")
        model_env = ROOT / "env" / f"{condition['model_argument']}.env"
        if condition.get("model_env_expected") == "absent" and model_env.exists():
            errors.append(f"unexpected Claude model environment exists: {relative(model_env)}")
        effective_base = env.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        if effective_base != condition["expected_base_url"]:
            errors.append(f"Claude base URL drift: expected {condition['expected_base_url']!r}, got {effective_base!r}")
        snapshot.update({"base_url": effective_base, "model_env_present": model_env.exists()})
    elif driver == "codex":
        snapshot["credential_environment_fields_present"] = sorted(
            name for name in ("CODEX_API_KEY", "OPENAI_API_KEY") if env.get(name)
        )
        home, home_errors = _external_home(env.get("ARENA_CODEX_HOME"), "ARENA_CODEX_HOME")
        errors.extend(home_errors)
        if home is not None:
            try:
                inventory, _ = credential_guard.inspect_source(driver, home)
                snapshot.update(
                    {
                        "auth_present": True,
                        "credential_source_schema": inventory["source_schema"],
                        "credential_secret_field_count": inventory["secret_field_count"],
                        "redacted_credential_structure_sha256": inventory[
                            "redacted_credential_structure_sha256"
                        ],
                        "redacted_home_inventory_sha256": inventory[
                            "redacted_structural_inventory_sha256"
                        ],
                    }
                )
            except credential_guard.CredentialGuardError as exc:
                errors.append(f"Codex credential source invalid: {exc}")
    else:
        snapshot["credential_environment_fields_present"] = sorted(
            name for name in ("KIMI_API_KEY", "MOONSHOT_API_KEY") if env.get(name)
        )
        raw_home = env.get("ARENA_KIMI_HOME") or str(Path.home() / ".kimi-arena")
        home, home_errors = _external_home(raw_home, "ARENA_KIMI_HOME")
        errors.extend(home_errors)
        if home is not None:
            try:
                inventory, _ = credential_guard.inspect_source(driver, home)
                snapshot.update(
                    {
                        "credential_source_schema": inventory["source_schema"],
                        "credential_secret_field_count": inventory["secret_field_count"],
                        "redacted_credential_structure_sha256": inventory[
                            "redacted_credential_structure_sha256"
                        ],
                        "redacted_config_sha256": inventory["redacted_structural_inventory_sha256"],
                        "redacted_home_inventory_sha256": inventory[
                            "redacted_structural_inventory_sha256"
                        ],
                    }
                )
            except credential_guard.CredentialGuardError as exc:
                errors.append(f"Kimi credential source invalid: {exc}")
    snapshot["sha256"] = sha256_bytes(canonical_json({key: value for key, value in snapshot.items() if key != "sha256"}))
    return snapshot, errors


def tracked_worktree_dirty() -> bool:
    return subprocess.run(
        ["git", "diff", "--quiet"], cwd=ROOT, check=False
    ).returncode != 0 or subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=ROOT, check=False
    ).returncode != 0


def preflight_manifest(manifest: dict[str, Any], condition_ids: set[str], env: dict[str, str]) -> dict[str, dict[str, Any]]:
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("manifest preflight failed:\n- " + "\n- ".join(errors))
    if tracked_worktree_dirty():
        raise ValueError("no-API treatment preflight failed:\n- harness has tracked worktree or index changes")
    snapshots: dict[str, dict[str, Any]] = {}
    configuration_lock = load_json(ROOT / CONFIG_LOCK_REL)
    frozen_set_sha = sha256_bytes(canonical_json(manifest.get("frozen_inputs") or []))
    for condition_id in sorted(condition_ids):
        condition = condition_map(manifest)[condition_id]
        condition_env = driver_environment(condition["driver"], env)
        if condition["driver"] == "kimi":
            condition_env["ARENA_KIMI_LABEL"] = condition["output_label"]
        snapshot, condition_errors = preflight_condition(condition, condition_env)
        snapshot["frozen_input_set_sha256"] = frozen_set_sha
        snapshot["sha256"] = sha256_bytes(
            canonical_json({key: value for key, value in snapshot.items() if key != "sha256"})
        )
        snapshots[condition_id] = snapshot
        errors.extend(condition_errors)
        expected = (configuration_lock.get("conditions") or {}).get(condition_id) or {}
        for key, expected_value in expected.items():
            if key == "isolated_home_policy":
                continue
            if snapshot.get(key) != expected_value:
                errors.append(
                    f"configuration lock mismatch for {condition_id}.{key}: expected {expected_value!r}, got {snapshot.get(key)!r}"
                )
    if errors:
        raise ValueError("no-API treatment preflight failed:\n- " + "\n- ".join(errors))
    return snapshots


def append_ledger(path: Path, row: dict[str, Any]) -> None:
    """Append one row under an advisory lock, then sync the file and directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_components(path.parent, "execution-ledger parent")
    parent_fd = _open_trusted_repository_directory(
        path.parent, "execution-ledger parent directory"
    )
    flags = os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = None
    try:
        descriptor = os.open(path.name, flags, 0o600, dir_fd=parent_fd)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        opened_before = _validate_opened_regular_file(
            parent_fd, path.name, descriptor, "execution ledger"
        )
        existing_payload = _read_descriptor_bytes(
            descriptor,
            limit=16 * 1024 * 1024,
            label="execution ledger",
        )
        existing = _parse_execution_ledger_payload(existing_payload)
        slot_id = row["slot_id"]
        if any(item.get("slot_id") == slot_id for item in existing):
            raise ValueError(f"execution ledger already contains {slot_id}")
        payload = (json.dumps(row, sort_keys=True) + "\n").encode()
        offset = 0
        while offset < len(payload):
            offset += os.write(descriptor, payload[offset:])
        os.fsync(descriptor)
        opened_after = _validate_opened_regular_file(
            parent_fd, path.name, descriptor, "execution ledger"
        )
        if (
            opened_before.st_dev,
            opened_before.st_ino,
        ) != (
            opened_after.st_dev,
            opened_after.st_ino,
        ):
            raise ValueError("execution ledger changed during append")
        complete_payload = existing_payload + payload
        observed_payload = _read_descriptor_bytes(
            descriptor,
            limit=16 * 1024 * 1024,
            label="execution ledger",
        )
        if observed_payload != complete_payload:
            raise ValueError("execution ledger bytes changed during append")
        observed_rows = _parse_execution_ledger_payload(observed_payload)
        if observed_rows != [*existing, row]:
            raise ValueError(
                "execution ledger append did not produce one complete expected row"
            )
        verified_after = _validate_opened_regular_file(
            parent_fd, path.name, descriptor, "execution ledger"
        )
        if _stable_file_fingerprint(opened_after) != _stable_file_fingerprint(
            verified_after
        ):
            raise ValueError("execution ledger changed during append verification")
        os.fsync(parent_fd)
    finally:
        if descriptor is not None:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)
        os.close(parent_fd)


def write_attempt_failure(manifest: dict[str, Any], slot: dict[str, Any], value: dict[str, Any]) -> str:
    path = ROOT / manifest["bout_dir"] / "ATTEMPT_FAILURES" / f"{slot['slot_id']}.json"
    if path.exists():
        raise FileExistsError(f"refusing to overwrite attempt-failure receipt {path}")
    write_json(path, value)
    return relative(path)


def _credential_home_for(driver: str, env: dict[str, str]) -> Path:
    variable = {
        "claude": "ARENA_CLAUDE_HOME",
        "codex": "ARENA_CODEX_HOME",
        "kimi": "ARENA_KIMI_HOME",
    }[driver]
    raw = env.get(variable)
    if not raw:
        raise credential_guard.CredentialGuardError(f"{variable} is unavailable to the security scanner")
    return Path(raw).resolve()


def scan_run_credentials(driver: str, env: dict[str, str], run_dir: Path, receipt_name: str) -> dict[str, Any]:
    """Scan exact exposed credentials without putting their values on a command line."""
    receipt_path = run_dir / receipt_name
    if receipt_path.exists() or receipt_path.is_symlink():
        raise credential_guard.CredentialGuardError("target-created credential scan receipt path")
    environment_secrets = []
    if driver == "claude":
        environment_secrets = [
            env.get("ANTHROPIC_API_KEY", ""),
            env.get("ANTHROPIC_AUTH_TOKEN", ""),
        ]
    receipt = credential_guard.scan_artifacts(
        driver,
        _credential_home_for(driver, env),
        [run_dir],
        environment_secrets=environment_secrets,
    )
    write_json(receipt_path, receipt)
    if not receipt["pass"]:
        raise SecretLeakError("credential scan detected a leak or unsafe filesystem entry")
    return receipt


def _safe_path_component(value: Any, label: str) -> str:
    component = str(value)
    if component in {"", ".", ".."} or Path(component).name != component:
        raise ValueError(f"unsafe {label}")
    return component


def _directory_open_flags() -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return flags


def _reject_symlink_components(path: Path, label: str) -> None:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current /= component
        if current.is_symlink():
            raise ValueError(f"{label} must not contain a symlink component")


def prepare_quarantine(
    manifest: dict[str, Any],
    slot: dict[str, Any],
    *,
    base_override: Path | None = None,
    ephemeral: bool = False,
) -> dict[str, Any]:
    """Open and retain the exact safe destination before target execution."""
    raw_base = str(base_override) if base_override is not None else os.environ.get("ARENA_QUARANTINE_DIR")
    unresolved = Path(raw_base).expanduser() if raw_base else Path.home() / ".agent-arena-quarantine"
    unresolved = Path(os.path.abspath(unresolved))
    _reject_symlink_components(unresolved, "secret quarantine root")
    unresolved.mkdir(parents=True, mode=0o700, exist_ok=True)
    _reject_symlink_components(unresolved, "secret quarantine root")
    metadata = unresolved.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise ValueError("secret quarantine root must be a real directory")
    base = unresolved.resolve(strict=True)
    try:
        base.relative_to(ROOT.resolve())
    except ValueError:
        pass
    else:
        raise ValueError("secret quarantine must be outside the Agent Arena repository")
    if (
        base != unresolved
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(base.stat().st_mode) & 0o077
    ):
        raise ValueError("secret quarantine root must not be accessible by group or other users")
    experiment_id = _safe_path_component(manifest["experiment_id"], "quarantine experiment ID")
    slot_id = _safe_path_component(slot["slot_id"], "quarantine slot ID")
    parent_fd = os.open(base.parent, _directory_open_flags())
    try:
        base_fd = os.open(base.name, _directory_open_flags(), dir_fd=parent_fd)
    except BaseException:
        os.close(parent_fd)
        raise
    try:
        base_stat = os.fstat(base_fd)
        attached_base = os.stat(base.name, dir_fd=parent_fd, follow_symlinks=False)
        if (base_stat.st_dev, base_stat.st_ino) != (attached_base.st_dev, attached_base.st_ino):
            raise ValueError("secret quarantine root changed during preparation")
        try:
            os.mkdir(experiment_id, mode=0o700, dir_fd=base_fd)
        except FileExistsError:
            existing = os.stat(experiment_id, dir_fd=base_fd, follow_symlinks=False)
            if not stat.S_ISDIR(existing.st_mode) or stat.S_ISLNK(existing.st_mode):
                raise ValueError("secret quarantine experiment directory must be a real directory")
        experiment_fd = os.open(experiment_id, _directory_open_flags(), dir_fd=base_fd)
        try:
            os.fchmod(experiment_fd, 0o700)
            experiment_stat = os.fstat(experiment_fd)
            attached_experiment = os.stat(
                experiment_id, dir_fd=base_fd, follow_symlinks=False
            )
            if (experiment_stat.st_dev, experiment_stat.st_ino) != (
                attached_experiment.st_dev,
                attached_experiment.st_ino,
            ):
                raise ValueError("secret quarantine experiment directory changed during preparation")
            if (
                not stat.S_ISDIR(experiment_stat.st_mode)
                or experiment_stat.st_uid != os.getuid()
                or stat.S_IMODE(experiment_stat.st_mode) & 0o077
            ):
                raise ValueError("secret quarantine experiment directory has unsafe permissions")
            if experiment_stat.st_dev != ROOT.stat().st_dev:
                raise ValueError(
                    "secret quarantine must share a filesystem with the repository for atomic rename"
                )
            for destination_name in (slot_id, f"{slot_id}--stage"):
                try:
                    os.stat(destination_name, dir_fd=experiment_fd, follow_symlinks=False)
                except (FileNotFoundError, OSError, RuntimeError):
                    pass
                else:
                    raise FileExistsError(
                        f"refusing to overwrite secret quarantine {base / experiment_id / destination_name}"
                    )
        except BaseException:
            os.close(experiment_fd)
            raise
    except BaseException:
        os.close(base_fd)
        os.close(parent_fd)
        raise
    return {
        "parent_fd": parent_fd,
        "base_fd": base_fd,
        "experiment_fd": experiment_fd,
        "base_name": base.name,
        "experiment_id": experiment_id,
        "slot_id": slot_id,
        "base_stat": (base_stat.st_dev, base_stat.st_ino),
        "experiment_stat": (experiment_stat.st_dev, experiment_stat.st_ino),
        "base_path": base,
        "ephemeral": ephemeral,
        "closed": False,
    }


def close_quarantine(handle: dict[str, Any] | None) -> None:
    if not handle or handle.get("closed"):
        return
    for key in ("experiment_fd", "base_fd", "parent_fd"):
        try:
            os.close(handle[key])
        except OSError:
            pass
    handle["closed"] = True


def prepare_emergency_quarantine(
    manifest: dict[str, Any], slot: dict[str, Any]
) -> dict[str, Any]:
    base = Path(tempfile.mkdtemp(prefix="arena-plan-emergency-quarantine.", dir=SAFE_TEMP_ROOT))
    base.chmod(0o700)
    try:
        return prepare_quarantine(
            manifest,
            slot,
            base_override=base,
            ephemeral=True,
        )
    except BaseException:
        try:
            base.rmdir()
        except OSError:
            pass
        raise


def dispose_quarantine(handle: dict[str, Any] | None) -> None:
    if not handle or handle.get("closed"):
        return
    if handle.get("ephemeral"):
        try:
            os.rmdir(handle["experiment_id"], dir_fd=handle["base_fd"])
            os.rmdir(handle["base_name"], dir_fd=handle["parent_fd"])
        except OSError as exc:
            if exc.errno not in {errno.ENOTEMPTY, errno.EEXIST}:
                close_quarantine(handle)
                raise
    close_quarantine(handle)


def quarantine_destination(manifest: dict[str, Any], slot: dict[str, Any]) -> Path:
    """Compatibility probe that validates and closes the preopened destination."""
    handle = prepare_quarantine(manifest, slot)
    try:
        return handle["base_path"] / handle["experiment_id"] / handle["slot_id"]
    finally:
        close_quarantine(handle)


def _validate_quarantine_handle(handle: dict[str, Any], destination_name: str) -> None:
    if handle.get("closed"):
        raise ValueError("secret quarantine descriptor is closed")
    base_stat = os.fstat(handle["base_fd"])
    experiment_stat = os.fstat(handle["experiment_fd"])
    attached_base = os.stat(
        handle["base_name"], dir_fd=handle["parent_fd"], follow_symlinks=False
    )
    attached_experiment = os.stat(
        handle["experiment_id"], dir_fd=handle["base_fd"], follow_symlinks=False
    )
    if (base_stat.st_dev, base_stat.st_ino) != handle["base_stat"] or (
        attached_base.st_dev,
        attached_base.st_ino,
    ) != handle["base_stat"]:
        raise ValueError("prevalidated secret quarantine root is no longer attached")
    if (experiment_stat.st_dev, experiment_stat.st_ino) != handle["experiment_stat"] or (
        attached_experiment.st_dev,
        attached_experiment.st_ino,
    ) != handle["experiment_stat"]:
        raise ValueError("prevalidated secret quarantine experiment directory is no longer attached")
    if stat.S_IMODE(base_stat.st_mode) & 0o077 or stat.S_IMODE(experiment_stat.st_mode) & 0o077:
        raise ValueError("prevalidated secret quarantine permissions changed")
    absolute_base = os.stat(handle["base_path"], follow_symlinks=False)
    absolute_experiment = os.stat(
        handle["base_path"] / handle["experiment_id"], follow_symlinks=False
    )
    if (absolute_base.st_dev, absolute_base.st_ino) != handle["base_stat"]:
        raise ValueError("prevalidated secret quarantine root is no longer path-reachable")
    if (absolute_experiment.st_dev, absolute_experiment.st_ino) != handle["experiment_stat"]:
        raise ValueError(
            "prevalidated secret quarantine experiment directory is no longer path-reachable"
        )
    try:
        os.stat(destination_name, dir_fd=handle["experiment_fd"], follow_symlinks=False)
    except FileNotFoundError:
        return
    raise FileExistsError(f"refusing to overwrite secret quarantine destination {destination_name}")


def _rename_noreplace(source: Path, destination_fd: int, destination_name: str) -> None:
    function = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
    if function is None:
        raise OSError("renameat2 with RENAME_NOREPLACE is unavailable")
    function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    function.restype = ctypes.c_int
    result = function(
        AT_FDCWD,
        os.fsencode(str(source)),
        destination_fd,
        os.fsencode(destination_name),
        RENAME_NOREPLACE,
    )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise FileExistsError(f"refusing to overwrite secret quarantine destination {destination_name}")
    raise OSError(error_number, os.strerror(error_number), str(source))


def quarantine_run(
    manifest: dict[str, Any],
    slot: dict[str, Any],
    run_dir: Path,
    *,
    handle: dict[str, Any] | None = None,
    destination_kind: str = "run",
    reason: str = "security_quarantine_after_secret_scan",
) -> dict[str, Any]:
    owned_handle = handle is None
    handle = handle or prepare_quarantine(manifest, slot)
    if destination_kind not in {"run", "stage"}:
        raise ValueError("unsupported quarantine destination kind")
    destination_name = handle["slot_id"] + ("--stage" if destination_kind == "stage" else "")
    source_metadata = run_dir.lstat()
    if not stat.S_ISDIR(source_metadata.st_mode) or stat.S_ISLNK(source_metadata.st_mode):
        raise ValueError("quarantine source must be a real directory")
    entry_count = 0
    regular_file_bytes = 0
    if run_dir.is_dir():
        for path in sorted(run_dir.rglob("*")):
            entry_count += 1
            try:
                metadata = path.lstat()
            except OSError:
                continue
            if stat.S_ISREG(metadata.st_mode):
                regular_file_bytes += metadata.st_size
    receipt = {
        "schema_version": 1,
        "experiment_id": manifest["experiment_id"],
        "manifest_freeze_id": manifest["freeze_id"],
        "slot_id": slot["slot_id"],
        "reason": reason,
        "destination_kind": destination_kind,
        "quarantined_at": utc_now(),
        "quarantined_entry_count": entry_count,
        "quarantined_regular_file_bytes": regular_file_bytes,
        "content_published": False,
        "fallback_destination": bool(handle.get("ephemeral")),
        "quarantine_destination": str(
            handle["base_path"] / handle["experiment_id"] / destination_name
        ),
    }
    suffix = ".stage.json" if destination_kind == "stage" else ".json"
    receipt_path = ROOT / manifest["bout_dir"] / "QUARANTINE" / f"{slot['slot_id']}{suffix}"
    receipt_relative = str(receipt_path.relative_to(ROOT))
    receipt_created = False
    try:
        _validate_quarantine_handle(handle, destination_name)
        try:
            receipt_sha256 = write_json_exclusive(receipt_path, receipt)
            receipt_created = True
        except FileExistsError as exc:
            raise FileExistsError(
                f"refusing to overwrite quarantine receipt {receipt_path}"
            ) from exc
        try:
            _rename_noreplace(run_dir, handle["experiment_fd"], destination_name)
        except BaseException:
            if receipt_created:
                unlink_file_durable(receipt_path)
            raise
        return {
            "succeeded": True,
            "receipt": receipt_relative,
            "receipt_sha256": receipt_sha256,
        }
    finally:
        if owned_handle:
            close_quarantine(handle)


def quarantine_with_fallback(
    manifest: dict[str, Any],
    slot: dict[str, Any],
    source: Path,
    *,
    primary: dict[str, Any],
    fallback: dict[str, Any],
    destination_kind: str = "run",
    reason: str = "security_quarantine_after_secret_scan",
) -> dict[str, Any]:
    try:
        return quarantine_run(
            manifest,
            slot,
            source,
            handle=primary,
            destination_kind=destination_kind,
            reason=reason,
        )
    except BaseException as primary_error:
        if not source.exists() and not source.is_symlink():
            raise
        try:
            result = quarantine_run(
                manifest,
                slot,
                source,
                handle=fallback,
                destination_kind=destination_kind,
                reason=reason,
            )
        except BaseException as fallback_error:
            raise RuntimeError(
                "both primary and emergency atomic quarantine destinations failed"
            ) from fallback_error
        result["primary_destination_error_type"] = type(primary_error).__name__
        return result


def quarantine_destination_issues(receipt: dict[str, Any]) -> list[str]:
    """Recheck aggregate preservation evidence without publishing quarantined content."""
    raw_destination = receipt.get("quarantine_destination")
    if not isinstance(raw_destination, str) or not Path(raw_destination).is_absolute():
        return ["quarantine destination is not an absolute path"]
    unresolved = Path(raw_destination)
    try:
        metadata = unresolved.lstat()
        destination = unresolved.resolve(strict=True)
        destination.relative_to(ROOT.resolve())
    except FileNotFoundError:
        return ["quarantine destination is missing"]
    except (OSError, RuntimeError):
        return ["quarantine destination is unreadable"]
    except ValueError:
        pass
    else:
        return ["quarantine destination is inside the repository"]
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        return ["quarantine destination is not a real directory"]
    try:
        parent_metadata = destination.parent.lstat()
    except OSError:
        return ["quarantine destination parent is unreadable"]
    if (
        not stat.S_ISDIR(parent_metadata.st_mode)
        or stat.S_ISLNK(parent_metadata.st_mode)
        or parent_metadata.st_uid != os.getuid()
        or stat.S_IMODE(parent_metadata.st_mode) & 0o077
    ):
        return ["quarantine destination parent has unsafe ownership or permissions"]
    entry_count = 0
    regular_file_bytes = 0
    try:
        for path in sorted(destination.rglob("*")):
            entry_count += 1
            item_metadata = path.lstat()
            if stat.S_ISREG(item_metadata.st_mode):
                regular_file_bytes += item_metadata.st_size
    except OSError:
        return ["quarantine destination inventory is unreadable"]
    issues = []
    if entry_count != receipt.get("quarantined_entry_count"):
        issues.append("quarantine destination entry count changed")
    if regular_file_bytes != receipt.get("quarantined_regular_file_bytes"):
        issues.append("quarantine destination regular-file bytes changed")
    return issues


def write_quarantine_failure(
    manifest: dict[str, Any], slot: dict[str, Any], run_dir: Path, error: BaseException
) -> dict[str, Any]:
    """Preserve auditable failure state if the prevalidated atomic quarantine unexpectedly fails."""
    receipt_path = ROOT / manifest["bout_dir"] / "QUARANTINE" / f"{slot['slot_id']}.failed.json"
    if receipt_path.exists() or receipt_path.is_symlink():
        raise FileExistsError(f"refusing to overwrite quarantine-failure receipt {receipt_path}")
    receipt = {
        "schema_version": 1,
        "experiment_id": manifest["experiment_id"],
        "manifest_freeze_id": manifest["freeze_id"],
        "slot_id": slot["slot_id"],
        "reason": "atomic_security_quarantine_failed",
        "failed_at": utc_now(),
        "error_type": type(error).__name__,
        "run_dir_retained_for_manual_recovery": relative(run_dir),
        "content_published": False,
    }
    receipt_sha256 = write_json_exclusive(receipt_path, receipt)
    return {
        "succeeded": False,
        "receipt": relative(receipt_path),
        "receipt_sha256": receipt_sha256,
    }


def raw_attempt_has_attributable_activity(driver: str, run_dir: Path) -> bool:
    """Fail closed when deciding whether an interrupted attempt was pre-attribution."""
    if not run_dir.is_dir():
        return False
    events, malformed = iter_jsonl(run_dir / "transcript.jsonl")
    if malformed:
        return True
    try:
        output, _ = extract_final_output(driver, run_dir, events)
        calls, unknown = detect_tool_events(driver, events, run_dir)
    except (OSError, ValueError, json.JSONDecodeError):
        return True
    workspace = run_dir / "workspace.diff"
    response_activity = any(
        (driver == "claude" and event.get("type") == "assistant")
        or (driver == "codex" and isinstance(event.get("item"), dict))
        or (driver == "kimi" and event.get("role") == "assistant")
        for event in events
    )
    if driver == "codex":
        session, session_malformed = iter_jsonl(run_dir / "session.jsonl")
        if session_malformed:
            return True
        response_activity = response_activity or any(
            event.get("type") == "response_item"
            and isinstance(event.get("payload"), dict)
            and event["payload"].get("role") == "assistant"
            for event in session
        )
    elif driver == "kimi":
        wire, wire_malformed = iter_jsonl(run_dir / "wire.jsonl")
        if wire_malformed:
            return True
        response_activity = response_activity or any(
            event.get("type") == "llm.response" for event in wire
        )
    return bool(
        output
        or calls
        or unknown
        or response_activity
        or (workspace.is_file() and workspace.stat().st_size)
    )


def _process_record(pid: int) -> dict[str, Any] | None:
    try:
        raw = (Path("/proc") / str(pid) / "stat").read_text()
        fields = raw[raw.rfind(")") + 2 :].split()
        if len(fields) < 20:
            return None
        return {
            "pid": pid,
            "state": fields[0],
            "ppid": int(fields[1]),
            "process_group": int(fields[2]),
            "start_time": int(fields[19]),
        }
    except (OSError, ValueError, IndexError):
        return None


def _direct_child_records() -> list[dict[str, Any]]:
    runner_pid = os.getpid()
    records = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        record = _process_record(int(entry.name))
        if record is not None and record["ppid"] == runner_pid:
            records.append(record)
    return sorted(records, key=lambda item: item["pid"])


def _reap_zombie_children() -> None:
    for record in _direct_child_records():
        if record["state"] != "Z":
            continue
        try:
            os.waitpid(record["pid"], os.WNOHANG)
        except (ChildProcessError, ProcessLookupError):
            pass


def _live_direct_child_records() -> list[dict[str, Any]]:
    _reap_zombie_children()
    return [record for record in _direct_child_records() if record["state"] != "Z"]


def prepare_child_subreaper() -> dict[str, Any]:
    """Claim exclusive adoption of target descendants before the target can fork."""
    prior = process_child_subreaper()
    process_child_subreaper(1)
    try:
        if process_child_subreaper() != 1:
            raise RuntimeError("child-subreaper state did not activate")
        existing = _direct_child_records()
        if existing:
            raise RuntimeError(
                "runner already has child processes; exclusive target adoption is unavailable"
            )
    except BaseException:
        process_child_subreaper(prior)
        raise
    return {"prior": prior, "active": True}


def close_child_subreaper(handle: dict[str, Any] | None) -> None:
    if not handle or not handle.get("active"):
        return
    _reap_zombie_children()
    if _direct_child_records():
        raise RuntimeError("refusing to release child-subreaper state with descendants present")
    process_child_subreaper(int(handle["prior"]))
    handle["active"] = False


def _signal_adopted_children(signum: int) -> None:
    for record in _live_direct_child_records():
        current = _process_record(record["pid"])
        if (
            current is None
            or current["ppid"] != os.getpid()
            or current["start_time"] != record["start_time"]
        ):
            continue
        try:
            os.kill(record["pid"], signum)
        except ProcessLookupError:
            pass


def _current_cgroup_parent() -> Path:
    entries = [line for line in Path("/proc/self/cgroup").read_text().splitlines() if line]
    if len(entries) != 1 or not entries[0].startswith("0::/"):
        raise RuntimeError("a unified cgroup-v2 process hierarchy is required")
    relative_cgroup = entries[0].split("::", 1)[1].lstrip("/")
    root = CGROUP_ROOT.resolve(strict=True)
    parent = (root / relative_cgroup).resolve(strict=True)
    parent.relative_to(root)
    if parent.is_symlink() or not parent.is_dir():
        raise RuntimeError("current cgroup-v2 parent is not a real directory")
    return parent


def process_scope_capability() -> str:
    parent = _current_cgroup_parent()
    if not os.access(parent, os.W_OK) or not (parent / "cgroup.kill").is_file():
        raise RuntimeError("current cgroup-v2 parent is not delegated for scoped cleanup")
    prior_subreaper = process_child_subreaper()
    process_child_subreaper(1)
    try:
        if process_child_subreaper() != 1:
            raise RuntimeError("Linux child-subreaper containment is unavailable")
        name = f"arena-plan-capability-{os.getpid()}-{os.urandom(4).hex()}"
        parent_fd = os.open(parent, _directory_open_flags())
        scope_fd: int | None = None
        created = False
        try:
            os.mkdir(name, dir_fd=parent_fd)
            created = True
            scope_fd = os.open(name, _directory_open_flags(), dir_fd=parent_fd)
            for entry, flags in (
                ("cgroup.procs", os.O_WRONLY | os.O_CLOEXEC),
                ("cgroup.kill", os.O_WRONLY | os.O_CLOEXEC),
                ("cgroup.events", os.O_RDONLY | os.O_CLOEXEC),
            ):
                descriptor = os.open(entry, flags, dir_fd=scope_fd)
                os.close(descriptor)
        finally:
            try:
                if scope_fd is not None:
                    os.close(scope_fd)
                if created:
                    os.rmdir(name, dir_fd=parent_fd)
            finally:
                os.close(parent_fd)
    finally:
        process_child_subreaper(prior_subreaper)
    return PROCESS_CONTAINMENT


def prepare_process_scope(slot: dict[str, Any]) -> dict[str, Any]:
    """Create dual cgroup/subreaper containment before any target process exists."""
    parent = _current_cgroup_parent()
    process_scope_capability()
    subreaper = prepare_child_subreaper()
    slot_id = _safe_path_component(slot["slot_id"], "process-scope slot ID")
    name = f"arena-plan-{sha256_bytes(slot_id.encode())[:20]}"
    try:
        parent_fd = os.open(parent, _directory_open_flags())
    except BaseException:
        close_child_subreaper(subreaper)
        raise
    scope_created = False
    scope_fd: int | None = None
    attach_fd: int | None = None
    try:
        os.mkdir(name, dir_fd=parent_fd)
        scope_created = True
        scope_fd = os.open(name, _directory_open_flags(), dir_fd=parent_fd)
    except BaseException:
        if scope_created:
            try:
                os.rmdir(name, dir_fd=parent_fd)
            except OSError:
                pass
        os.close(parent_fd)
        close_child_subreaper(subreaper)
        raise
    try:
        assert scope_fd is not None
        scope_stat = os.fstat(scope_fd)
        attached = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if (scope_stat.st_dev, scope_stat.st_ino) != (attached.st_dev, attached.st_ino):
            raise RuntimeError("process cgroup changed during preparation")
        attach_fd = os.open(
            "cgroup.procs",
            os.O_WRONLY | os.O_CLOEXEC,
            dir_fd=scope_fd,
        )
        kill_probe = os.open("cgroup.kill", os.O_WRONLY | os.O_CLOEXEC, dir_fd=scope_fd)
        os.close(kill_probe)
    except BaseException:
        if attach_fd is not None:
            os.close(attach_fd)
        os.close(scope_fd)
        try:
            os.rmdir(name, dir_fd=parent_fd)
        finally:
            os.close(parent_fd)
            close_child_subreaper(subreaper)
        raise
    return {
        "parent_fd": parent_fd,
        "scope_fd": scope_fd,
        "attach_fd": attach_fd,
        "name": name,
        "path": parent / name,
        "stat": (scope_stat.st_dev, scope_stat.st_ino),
        "subreaper": subreaper,
        "closed": False,
        "removed": False,
    }


def close_process_scope(handle: dict[str, Any] | None) -> None:
    if not handle:
        return
    if not handle.get("closed"):
        if not handle.get("removed") and handle.get("scope_fd") is not None:
            try:
                if not _process_scope_populated(handle):
                    os.rmdir(handle["name"], dir_fd=handle["parent_fd"])
                    handle["removed"] = True
            except OSError:
                pass
        for key in ("attach_fd", "scope_fd", "parent_fd"):
            descriptor = handle.get(key)
            if descriptor is None:
                continue
            try:
                os.close(descriptor)
            except OSError:
                pass
            handle[key] = None
        handle["closed"] = True
    subreaper = handle.get("subreaper")
    if subreaper and subreaper.get("active") and not _direct_child_records():
        try:
            close_child_subreaper(subreaper)
        except (OSError, RuntimeError) as exc:
            handle["subreaper_close_error"] = type(exc).__name__


def attach_process_scope(handle: dict[str, Any]) -> None:
    """Child-side Popen hook: enter the frozen cgroup before exec, then drop the descriptor."""
    descriptor = int(handle["attach_fd"])
    try:
        os.write(descriptor, b"0\n")
    finally:
        os.close(descriptor)


def _read_cgroup_file(handle: dict[str, Any], name: str) -> str:
    descriptor = os.open(name, os.O_RDONLY | os.O_CLOEXEC, dir_fd=handle["scope_fd"])
    try:
        chunks = []
        while True:
            chunk = os.read(descriptor, 4096)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks).decode(errors="replace")
    finally:
        os.close(descriptor)


def _process_scope_populated(handle: dict[str, Any]) -> bool:
    fields = dict(
        line.split(maxsplit=1)
        for line in _read_cgroup_file(handle, "cgroup.events").splitlines()
        if " " in line
    )
    if fields.get("populated") not in {"0", "1"}:
        raise RuntimeError("process cgroup has no trustworthy populated state")
    return fields["populated"] == "1"


def _process_scope_pids(handle: dict[str, Any]) -> list[int]:
    values = []
    for raw in _read_cgroup_file(handle, "cgroup.procs").splitlines():
        try:
            value = int(raw)
        except ValueError as exc:
            raise RuntimeError("process cgroup contains a malformed PID") from exc
        if value > 1 and value != os.getpid():
            values.append(value)
    return sorted(set(values))


def _signal_process_scope(handle: dict[str, Any], signum: int) -> None:
    for pid in _process_scope_pids(handle):
        try:
            os.kill(pid, signum)
        except ProcessLookupError:
            pass


def _kill_process_scope(handle: dict[str, Any]) -> None:
    descriptor = os.open("cgroup.kill", os.O_WRONLY | os.O_CLOEXEC, dir_fd=handle["scope_fd"])
    try:
        os.write(descriptor, b"1\n")
    finally:
        os.close(descriptor)


def _wait_for_contained_descendants_exit(
    handle: dict[str, Any],
    timeout_seconds: float,
    poll_interval: float,
    *,
    force: bool,
) -> bool:
    """Drain both cgroup members and escaped descendants adopted by the runner."""
    deadline = time.monotonic() + timeout_seconds
    while True:
        populated = _process_scope_populated(handle)
        adopted = (
            _live_direct_child_records()
            if (handle.get("subreaper") or {}).get("active")
            else []
        )
        if not populated and not adopted:
            _reap_zombie_children()
            if not _process_scope_populated(handle) and not _live_direct_child_records():
                return True
        elif force:
            if populated:
                _kill_process_scope(handle)
            _signal_adopted_children(signal.SIGKILL)
        else:
            if populated:
                _signal_process_scope(handle, signal.SIGTERM)
            _signal_adopted_children(signal.SIGTERM)
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll_interval)


def _process_group_exists(process_group_id: int) -> bool:
    proc_root = Path("/proc")
    if proc_root.is_dir():
        saw_member = False
        for entry in proc_root.iterdir():
            if not entry.name.isdigit():
                continue
            try:
                raw = (entry / "stat").read_text()
                fields = raw[raw.rfind(")") + 2 :].split()
                state = fields[0]
                member_group = int(fields[2])
            except (OSError, ValueError, IndexError):
                continue
            if member_group == process_group_id:
                saw_member = True
                if state != "Z":
                    return True
        if saw_member:
            return False
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_for_process_group_exit(
    process: subprocess.Popen[Any],
    process_group_id: int,
    timeout_seconds: float,
    poll_interval: float,
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while True:
        process.poll()
        if not _process_group_exists(process_group_id):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll_interval)


def terminate_process_group(
    process: subprocess.Popen[Any],
    *,
    term_grace_seconds: float = 5.0,
    kill_grace_seconds: float = 5.0,
    poll_interval: float = 0.05,
) -> None:
    """Stop every process in the driver's session, even after its leader exits."""
    process_group_id = process.pid
    if process_group_id <= 1 or process_group_id == os.getpgrp():
        raise ValueError("refusing to signal the runner's own process group")
    try:
        os.killpg(process_group_id, signal.SIGTERM)
    except ProcessLookupError:
        process.poll()
        return
    if not _wait_for_process_group_exit(
        process,
        process_group_id,
        term_grace_seconds,
        poll_interval,
    ):
        try:
            os.killpg(process_group_id, signal.SIGKILL)
        except ProcessLookupError:
            process.poll()
            return
        if not _wait_for_process_group_exit(
            process,
            process_group_id,
            kill_grace_seconds,
            poll_interval,
        ):
            raise RuntimeError(f"target process group {process_group_id} survived SIGKILL")
    process.poll()


def terminate_process_scope(
    process: subprocess.Popen[Any] | None,
    handle: dict[str, Any],
    *,
    term_grace_seconds: float = 5.0,
    kill_grace_seconds: float = 5.0,
    poll_interval: float = 0.05,
) -> None:
    """Stop the original PGID, cgroup members, and escaped adopted descendants."""
    group_error: BaseException | None = None
    if process is not None:
        try:
            terminate_process_group(
                process,
                term_grace_seconds=term_grace_seconds,
                kill_grace_seconds=kill_grace_seconds,
                poll_interval=poll_interval,
            )
        except BaseException as exc:
            group_error = exc
    if not _wait_for_contained_descendants_exit(
        handle,
        term_grace_seconds,
        poll_interval,
        force=False,
    ):
        if not _wait_for_contained_descendants_exit(
            handle,
            kill_grace_seconds,
            poll_interval,
            force=True,
        ):
            raise RuntimeError(
                "target process cgroup or an escaped adopted descendant survived forced cleanup"
            )
    if process is not None and _process_group_exists(process.pid):
        if group_error is not None:
            raise RuntimeError("target process group survived cleanup") from group_error
        raise RuntimeError("target process group survived cleanup")
    if _process_scope_populated(handle):
        raise RuntimeError("target process cgroup remained populated after cleanup")
    _reap_zombie_children()
    if _direct_child_records():
        raise RuntimeError("escaped target descendant remained after child-subreaper cleanup")
    os.rmdir(handle["name"], dir_fd=handle["parent_fd"])
    handle["removed"] = True
    close_process_scope(handle)
    if handle.get("subreaper_close_error"):
        raise RuntimeError("child-subreaper state could not be restored after cleanup")


def validate_prior_attempt_provenance(manifest: dict[str, Any], ledger: list[dict[str, Any]]) -> list[str]:
    """Recheck immutable anchors before a resumed command may make another paid call."""
    errors: list[str] = []
    slots = {
        slot["slot_id"]: slot
        for slot in [*(manifest.get("schedule") or []), *(manifest.get("reserve_slots") or [])]
    }
    for row in ledger:
        if not isinstance(row, dict):
            continue
        if row.get("process_group_cleaned") is not True:
            errors.append(
                f"{row.get('slot_id')}: missing or unresolved process-scope cleanup evidence blocks further execution"
            )
        if row.get("staged_attempt_retained") is not False:
            errors.append(
                f"{row.get('slot_id')}: missing or retained staged-attempt evidence blocks further execution"
            )
        if row.get("staged_attempt_retained") is True:
            raw_stage_path = row.get("staged_attempt_path")
            if isinstance(raw_stage_path, str):
                try:
                    stage_path = Path(raw_stage_path).resolve(strict=True)
                    stage_path.relative_to(ROOT.resolve())
                except (OSError, RuntimeError):
                    errors.append(
                        f"{row.get('slot_id')}: retained staged-attempt path is missing"
                    )
                except ValueError:
                    if Path(raw_stage_path).is_symlink() or not stage_path.is_dir():
                        errors.append(
                            f"{row.get('slot_id')}: retained staged-attempt path is unsafe"
                        )
                else:
                    errors.append(
                        f"{row.get('slot_id')}: retained staged-attempt path is inside the repository"
                    )
        slot = slots.get(row.get("slot_id"))
        if slot is None:
            continue
        expected_run_dir = output_dir_for(manifest, slot)
        retained_run_dir = expected_run_dir.exists() or expected_run_dir.is_symlink()
        artifact_anchor = row.get("artifact_manifest_sha256")
        if retained_run_dir and artifact_anchor is None:
            errors.append(f"{row.get('slot_id')}: retained run directory lacks an artifact anchor")
        elif artifact_anchor is not None:
            if row.get("analysis_eligible") is True:
                _, row_errors = validate_run_provenance(manifest, slot, row)
                errors.extend(row_errors)
            else:
                _, record_kind, row_errors = validate_artifact_anchor(manifest, slot, row)
                if record_kind == "normalized_run":
                    _, row_errors = validate_run_provenance(manifest, slot, row)
                    errors.extend(row_errors)
                else:
                    errors.extend(row_errors)
                if record_kind not in {"normalized_run", "failed_attempt"}:
                    errors.append(f"{row.get('slot_id')}: ineligible attempt has no valid artifact record kind")
        for path_key, hash_key in (
            ("failure_receipt", "failure_receipt_sha256"),
            ("quarantine_receipt", "quarantine_receipt_sha256"),
            ("quarantine_failure_receipt", "quarantine_failure_receipt_sha256"),
            ("stage_quarantine_receipt", "stage_quarantine_receipt_sha256"),
        ):
            raw_path = row.get(path_key)
            if raw_path is None:
                continue
            unresolved_path = ROOT / str(raw_path)
            try:
                path = unresolved_path.resolve()
                path.relative_to(ROOT.resolve())
            except (OSError, ValueError):
                errors.append(f"{row.get('slot_id')}: unsafe {path_key}")
                continue
            if unresolved_path.is_symlink() or not unresolved_path.is_file():
                errors.append(f"{row.get('slot_id')}: missing regular {path_key}")
            elif not re.fullmatch(r"[0-9a-f]{64}", str(row.get(hash_key) or "")):
                errors.append(f"{row.get('slot_id')}: {path_key} lacks a content hash")
            elif sha256_path(path) != row.get(hash_key):
                errors.append(f"{row.get('slot_id')}: {path_key} content hash mismatch")
            else:
                try:
                    receipt = load_json(path)
                except (OSError, json.JSONDecodeError) as exc:
                    errors.append(
                        f"{row.get('slot_id')}: malformed {path_key}: {type(exc).__name__}"
                    )
                    continue
                if not isinstance(receipt, dict):
                    errors.append(f"{row.get('slot_id')}: {path_key} is not an object")
                    continue
                for good, label in (
                    (receipt.get("experiment_id") == manifest.get("experiment_id"), "experiment ID"),
                    (receipt.get("manifest_freeze_id") == manifest.get("freeze_id"), "freeze ID"),
                    (receipt.get("slot_id") == row.get("slot_id"), "slot ID"),
                ):
                    if not good:
                        errors.append(f"{row.get('slot_id')}: {path_key} {label} mismatch")
                if path_key == "failure_receipt":
                    if not isinstance(receipt.get("process_group_cleaned"), bool):
                        errors.append(
                            f"{row.get('slot_id')}: failure receipt lacks process-group cleanup state"
                        )
                    elif receipt["process_group_cleaned"] is not row.get(
                        "process_group_cleaned"
                    ):
                        errors.append(
                            f"{row.get('slot_id')}: failure receipt and ledger cleanup state differ"
                        )
                    if receipt.get("process_group_cleaned") is False:
                        errors.append(
                            f"{row.get('slot_id')}: unresolved process-scope cleanup failure blocks further execution"
                        )
                    if not isinstance(receipt.get("staged_attempt_retained"), bool):
                        errors.append(
                            f"{row.get('slot_id')}: failure receipt lacks staged-attempt retention state"
                        )
                    elif receipt["staged_attempt_retained"] is not row.get(
                        "staged_attempt_retained"
                    ):
                        errors.append(
                            f"{row.get('slot_id')}: failure receipt and ledger staged-attempt state differ"
                        )
                    if receipt.get("staged_attempt_retained") is True:
                        errors.append(
                            f"{row.get('slot_id')}: retained staged attempt blocks further execution"
                        )
                    if receipt.get("staged_attempt_path") != row.get(
                        "staged_attempt_path"
                    ):
                        errors.append(
                            f"{row.get('slot_id')}: failure receipt and ledger staged-attempt path differ"
                        )
                    for (
                        embedded_key,
                        success_ledger_key,
                        success_hash_key,
                        failure_ledger_key,
                        failure_hash_key,
                    ) in (
                        (
                            "quarantine",
                            "quarantine_receipt",
                            "quarantine_receipt_sha256",
                            "quarantine_failure_receipt",
                            "quarantine_failure_receipt_sha256",
                        ),
                        (
                            "stage_quarantine",
                            "stage_quarantine_receipt",
                            "stage_quarantine_receipt_sha256",
                            None,
                            None,
                        ),
                    ):
                        embedded = receipt.get(embedded_key)
                        succeeded = (
                            embedded.get("succeeded")
                            if isinstance(embedded, dict)
                            else None
                        )
                        embedded_path = (
                            embedded.get("receipt") if isinstance(embedded, dict) else None
                        )
                        expected_success = embedded_path if succeeded is True else None
                        expected_failure = embedded_path if succeeded is False else None
                        embedded_hash = (
                            embedded.get("receipt_sha256")
                            if isinstance(embedded, dict)
                            else None
                        )
                        expected_success_hash = (
                            embedded_hash if succeeded is True else None
                        )
                        expected_failure_hash = (
                            embedded_hash if succeeded is False else None
                        )
                        if expected_success != row.get(success_ledger_key):
                            errors.append(
                                f"{row.get('slot_id')}: failure receipt and ledger {embedded_key} evidence differ"
                            )
                        if expected_success_hash != row.get(success_hash_key):
                            errors.append(
                                f"{row.get('slot_id')}: failure receipt and ledger {embedded_key} hash differ"
                            )
                        if failure_ledger_key and expected_failure != row.get(
                            failure_ledger_key
                        ):
                            errors.append(
                                f"{row.get('slot_id')}: failure receipt and ledger {embedded_key} failure evidence differ"
                            )
                        if failure_hash_key and expected_failure_hash != row.get(
                            failure_hash_key
                        ):
                            errors.append(
                                f"{row.get('slot_id')}: failure receipt and ledger {embedded_key} failure hash differ"
                            )
                elif path_key == "quarantine_receipt" and receipt.get(
                    "destination_kind"
                ) != "run":
                    errors.append(
                        f"{row.get('slot_id')}: quarantine receipt has the wrong destination kind"
                    )
                elif path_key in {"quarantine_receipt", "stage_quarantine_receipt"}:
                    if (
                        path_key == "stage_quarantine_receipt"
                        and receipt.get("destination_kind") != "stage"
                    ):
                        errors.append(
                            f"{row.get('slot_id')}: stage quarantine receipt has the wrong destination kind"
                        )
                    errors.extend(
                        f"{row.get('slot_id')}: {issue}"
                        for issue in quarantine_destination_issues(receipt)
                    )
    return errors


def run_slots(
    manifest_path: Path,
    *,
    approval: str | None,
    requested_slots: set[str] | None,
    dry_run: bool,
    reserve_slot: str | None = None,
    replacement_for: str | None = None,
    exclusion_reason: str | None = None,
    test_only_crash_checkpoint: str | None = None,
) -> None:
    """Run under one bout-wide lock when crash-durable intents are frozen."""
    if not dry_run:
        require_strict_creation_umask("live execution")
    manifest, _manifest_snapshot = read_manifest_strict(
        manifest_path, label="execution manifest"
    )
    lock_fd: int | None = None
    if attempt_intent_enabled(manifest):
        lock_fd = acquire_execution_lock(manifest)
    try:
        _run_slots_locked(
            manifest_path,
            approval=approval,
            requested_slots=requested_slots,
            dry_run=dry_run,
            reserve_slot=reserve_slot,
            replacement_for=replacement_for,
            exclusion_reason=exclusion_reason,
            test_only_crash_checkpoint=test_only_crash_checkpoint,
        )
    finally:
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(lock_fd)


def _run_slots_locked(
    manifest_path: Path,
    *,
    approval: str | None,
    requested_slots: set[str] | None,
    dry_run: bool,
    reserve_slot: str | None = None,
    replacement_for: str | None = None,
    exclusion_reason: str | None = None,
    test_only_crash_checkpoint: str | None = None,
) -> None:
    if test_only_crash_checkpoint is not None:
        if test_only_crash_checkpoint not in SYNTHETIC_CRASH_CHECKPOINTS:
            raise ValueError("unknown synthetic attempt-crash checkpoint")
        if os.environ.get("ARENA_SYNTHETIC_ONLY") != "1":
            raise PermissionError("attempt crash injection is restricted to offline synthetic tests")
    manifest, manifest_snapshot = read_manifest_strict(
        manifest_path, label="execution manifest"
    )
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("manifest invalid:\n- " + "\n- ".join(errors))
    if manifest["phase"] == "confirmatory" and not dry_run and approval != manifest["freeze_id"]:
        raise PermissionError(
            "confirmatory execution is embargoed; after explicit user approval, pass --approval " + manifest["freeze_id"]
        )
    schedule = manifest["schedule"]
    ledger_path = ROOT / manifest["bout_dir"] / "EXECUTION.jsonl"
    ledger, _ledger_snapshot = read_execution_ledger(ledger_path)
    ledger_errors = validate_execution_ledger(manifest, ledger)
    if ledger_errors:
        raise ValueError("execution ledger is invalid:\n- " + "\n- ".join(ledger_errors))
    provenance_errors = validate_prior_attempt_provenance(manifest, ledger)
    if provenance_errors:
        raise ValueError("prior attempt provenance is invalid:\n- " + "\n- ".join(provenance_errors))
    budget_errors = validate_smoke_call_budget(manifest, ledger)
    if budget_errors:
        raise ValueError("smoke call budget is invalid:\n- " + "\n- ".join(budget_errors))
    if reserve_slot:
        if requested_slots:
            raise ValueError("--reserve and --slot cannot be combined")
        if not replacement_for or not exclusion_reason:
            raise ValueError("reserve execution requires --replacement-for and --exclusion-reason")
        allowed_reasons = set(manifest["exclusions"]["replace_only"])
        if exclusion_reason not in allowed_reasons:
            raise ValueError(f"replacement reason is not preregistered: {exclusion_reason}")
        reserve = next((slot for slot in manifest.get("reserve_slots") or [] if slot["slot_id"] == reserve_slot), None)
        if reserve is None:
            raise ValueError("reserve slot is not in the frozen manifest")
        replaced_row = next((row for row in ledger if row.get("slot_id") == replacement_for), None)
        if replaced_row is None or replaced_row.get("analysis_eligible") is not False:
            raise ValueError("the replaced attempt must exist in the ledger and be objectively ineligible")
        if manifest["phase"] == "confirmatory":
            pending = _confirmatory_pending_attempt(ledger)
            if pending is None or pending.get("slot_id") != replacement_for:
                raise ValueError(
                    "the reserve must replace the currently paused analysis-ineligible attempt"
                )
        if reserve["condition_id"] != replaced_row.get("condition_id"):
            raise ValueError("reserve and replaced attempt belong to different conditions")
        if exclusion_reason not in set(replaced_row.get("eligible_exclusion_reasons") or []):
            raise ValueError("replacement reason is not supported by the replaced attempt's recorded evidence")
        if any(row.get("replacement_for") == replacement_for for row in ledger):
            raise ValueError("the replaced attempt already has an executed replacement")
        if any(row.get("slot_id") == reserve_slot for row in ledger):
            raise ValueError("the selected reserve slot has already been attempted")
        condition_reserves = [
            slot
            for slot in manifest.get("reserve_slots") or []
            if slot["condition_id"] == reserve["condition_id"]
        ]
        attempted = {row.get("slot_id") for row in ledger}
        next_reserve = next((slot for slot in condition_reserves if slot["slot_id"] not in attempted), None)
        if next_reserve is None or next_reserve["slot_id"] != reserve_slot:
            raise ValueError("reserve execution must use the next frozen reserve index for its condition")
        runtime_reserve = dict(reserve)
        runtime_reserve["replacement_for"] = replacement_for
        runtime_reserve["exclusion_reason"] = exclusion_reason
        schedule = [runtime_reserve]
    else:
        attempted_primary = [
            row["slot_id"] for row in ledger if row.get("kind") == "primary"
        ]
        schedule = schedule[len(attempted_primary) :]
        if manifest["phase"] == "confirmatory":
            children = {
                row.get("replacement_for"): row
                for row in ledger
                if row.get("replacement_for") is not None
            }
            for primary_id in attempted_primary:
                row = next(item for item in ledger if item.get("slot_id") == primary_id)
                while row.get("analysis_eligible") is False and row.get("slot_id") in children:
                    row = children[row["slot_id"]]
                if row.get("analysis_eligible") is not True:
                    raise ValueError(
                        f"primary attempt {primary_id} has no eligible replacement; run its next reserve before resuming"
                    )
    if requested_slots and not reserve_slot:
        known = {slot["slot_id"] for slot in schedule}
        unknown = requested_slots - known
        if unknown:
            raise ValueError(f"requested slots are not pending primary slots: {sorted(unknown)}")
        selected = [slot for slot in schedule if slot["slot_id"] in requested_slots]
        if selected != schedule[: len(selected)]:
            raise ValueError("requested primary slots must be a contiguous prefix of the frozen pending order")
        schedule = selected
    if dry_run:
        for slot in schedule:
            command, _ = driver_command(manifest, slot)
            print(json.dumps({"slot_id": slot["slot_id"], "command": command}))
        return

    base_env = dict(os.environ)
    initial_preflight = preflight_manifest(manifest, {slot["condition_id"] for slot in schedule}, base_env)
    for slot in schedule:
        if manifest.get("smoke_continuation") is not None:
            continuation_errors = validate_manifest(manifest)
            if continuation_errors:
                raise ValueError(
                    "smoke predecessor or continuation drifted before the next call:\n- "
                    + "\n- ".join(continuation_errors)
                )
        run_dir = output_dir_for(manifest, slot)
        if run_dir.exists():
            raise FileExistsError(f"refusing to overwrite {run_dir}")
        existing_ledger, existing_ledger_snapshot = read_execution_ledger(
            ledger_path
        )
        existing_errors = validate_execution_ledger(manifest, existing_ledger)
        existing_errors.extend(validate_prior_attempt_provenance(manifest, existing_ledger))
        existing_errors.extend(
            validate_smoke_call_budget(manifest, existing_ledger, next_slot=slot)
        )
        if existing_errors:
            raise ValueError(
                "prior attempt provenance changed before the next call:\n- "
                + "\n- ".join(existing_errors)
            )
        if any(row.get("slot_id") == slot["slot_id"] for row in existing_ledger):
            raise ValueError(f"execution ledger already contains {slot['slot_id']}")
        prior_policy_signatures = {
            row.get("instruction_policy_signature_sha256")
            for row in existing_ledger
            if row.get("condition_id") == slot["condition_id"] and row.get("instruction_policy_signature_sha256")
        }
        if len(prior_policy_signatures) > 1:
            raise ValueError(f"execution ledger already contains policy drift for {slot['condition_id']}")
        expected_policy_signature = next(iter(prior_policy_signatures), None)
        command, env = driver_command(manifest, slot)
        current_preflight = preflight_manifest(manifest, {slot["condition_id"]}, env)[slot["condition_id"]]
        if current_preflight["sha256"] != initial_preflight[slot["condition_id"]]["sha256"]:
            raise ValueError(f"treatment preflight drifted before {slot['slot_id']}")
        quarantine_handle = prepare_quarantine(manifest, slot)
        emergency_quarantine_handle: dict[str, Any] | None = None
        try:
            emergency_quarantine_handle = prepare_emergency_quarantine(manifest, slot)
            process_scope = prepare_process_scope(slot)
        except BaseException:
            dispose_quarantine(emergency_quarantine_handle)
            close_quarantine(quarantine_handle)
            raise
        env["ARENA_HARNESS_COMMIT"] = current_preflight["harness_commit"]
        env["ARENA_HARNESS_TRACKED_DIRTY"] = "false"
        try:
            attempt_root, staged_run_dir, command, env = prepare_staged_driver(
                manifest, slot, env
            )
        except BaseException:
            try:
                terminate_process_scope(None, process_scope)
            finally:
                close_process_scope(process_scope)
                dispose_quarantine(emergency_quarantine_handle)
                close_quarantine(quarantine_handle)
            raise
        started = utc_now()
        intent_required = attempt_intent_enabled(manifest)
        attempt_intent_relative: str | None = None
        attempt_intent_sha256: str | None = None
        attempt_claim: dict[str, Any] | None = None
        attempt_intent_claimed = not intent_required
        launch_authorized = not intent_required
        record: dict[str, Any] | None = None
        driver_exit: int | None = None
        driver_process_spawned = False
        target_process_started = False
        target_process_returned = False
        process: subprocess.Popen[Any] | None = None
        process_group_cleaned = False
        staged_attempt_retained = False
        caught: BaseException | None = None
        synthetic_crash: SyntheticAttemptCrash | None = None
        quarantine: dict[str, Any] | None = None
        stage_quarantine: dict[str, Any] | None = None
        attributable_activity: bool | None = None
        cleanup_signal: int | None = None
        prior_dumpable = process_dumpable()
        dumpability_lowered = False
        watched_signals = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
        previous_signal_handlers = {signum: signal.getsignal(signum) for signum in watched_signals}

        def interrupt_active_attempt(signum: int, _frame: Any) -> None:
            for watched in watched_signals:
                signal.signal(watched, signal.SIG_IGN)
            raise OperatorTermination(signum)

        def record_cleanup_interruption(signum: int, _frame: Any) -> None:
            nonlocal cleanup_signal
            cleanup_signal = signum

        for signum in watched_signals:
            signal.signal(signum, interrupt_active_attempt)
        try:
            process_dumpable(0)
            dumpability_lowered = True
            if intent_required:
                synthetic_crash_checkpoint(test_only_crash_checkpoint, "pre_claim")
                attempt_intent_relative, attempt_intent_sha256 = claim_attempt_intent(
                    manifest,
                    slot,
                    current_preflight,
                    command,
                    test_only_crash_checkpoint=test_only_crash_checkpoint,
                )
                attempt_intent_claimed = True
                synthetic_crash_checkpoint(
                    test_only_crash_checkpoint, "post_claim_pre_spawn"
                )
                fresh_manifest, fresh_manifest_snapshot = read_manifest_strict(
                    manifest_path, label="execution manifest"
                )
                if (
                    fresh_manifest != manifest
                    or fresh_manifest_snapshot != manifest_snapshot
                ):
                    raise ValueError(
                        "execution manifest changed before process launch"
                    )
                attempt_claim = authorize_attempt_launch(
                    manifest,
                    slot,
                    existing_ledger,
                    existing_ledger_snapshot,
                )
                launch_authorized = True
            try:
                process = subprocess.Popen(
                    command,
                    cwd=attempt_root,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                    pass_fds=(process_scope["attach_fd"],),
                    preexec_fn=lambda: attach_process_scope(process_scope),
                )
            finally:
                if process_scope.get("attach_fd") is not None:
                    os.close(process_scope["attach_fd"])
                    process_scope["attach_fd"] = None
            driver_process_spawned = True
            synthetic_crash_checkpoint(test_only_crash_checkpoint, "post_spawn")
            driver_exit = process.wait()
            terminate_process_scope(process, process_scope)
            process_group_cleaned = True
            synthetic_crash_checkpoint(test_only_crash_checkpoint, "post_cleanup")
            recover_and_remove_staged_driver(attempt_root, staged_run_dir, run_dir)
            synthetic_crash_checkpoint(test_only_crash_checkpoint, "post_recovery")
            target_process_started = (run_dir / "target_started").is_file()
            target_process_returned = (run_dir / "target_returned").is_file()
            scan_run_credentials(
                condition_map(manifest)[slot["condition_id"]]["driver"],
                env,
                run_dir,
                "credential_scan.raw.json",
            )
            if driver_exit == 86:
                raise SecretLeakError("per-run credential-state scan failed")
            if driver_exit not in {0, None}:
                raise RuntimeError(f"driver wrapper exited with status {driver_exit}")
            record = observe_run(
                manifest,
                slot,
                run_dir,
                expected_policy_signature=expected_policy_signature,
                finalize_artifact_manifest=False,
            )
        except SyntheticAttemptCrash as exc:
            synthetic_crash = exc
        except BaseException as exc:  # ledger preservation also covers operator interruption
            caught = exc
        finally:
            if process is None:
                try:
                    terminate_process_scope(None, process_scope)
                    process_group_cleaned = True
                except BaseException as termination_exc:
                    if caught is None or not isinstance(caught, (KeyboardInterrupt, SystemExit)):
                        caught = termination_exc
            elif not process_group_cleaned:
                try:
                    terminate_process_scope(process, process_scope)
                    process_group_cleaned = True
                except BaseException as termination_exc:
                    if caught is None or not isinstance(caught, (KeyboardInterrupt, SystemExit)):
                        caught = termination_exc
                driver_exit = process.returncode
            if path_entry_exists(attempt_root) and process_group_cleaned:
                try:
                    recover_and_remove_staged_driver(attempt_root, staged_run_dir, run_dir)
                except BaseException as stage_exc:
                    if caught is None or not isinstance(caught, (KeyboardInterrupt, SystemExit)):
                        caught = stage_exc
                    if path_entry_exists(attempt_root):
                        try:
                            stage_quarantine = quarantine_with_fallback(
                                manifest,
                                slot,
                                attempt_root,
                                primary=quarantine_handle,
                                fallback=emergency_quarantine_handle,
                                destination_kind="stage",
                                reason="staged_recovery_failure_quarantine",
                            )
                        except BaseException as stage_quarantine_exc:
                            staged_attempt_retained = True
                            if caught is None or not isinstance(
                                caught, (KeyboardInterrupt, SystemExit)
                            ):
                                caught = stage_quarantine_exc
            if path_entry_exists(attempt_root):
                staged_attempt_retained = True
            if dumpability_lowered:
                try:
                    process_dumpable(prior_dumpable)
                except BaseException as dumpable_exc:
                    if caught is None or not isinstance(caught, (KeyboardInterrupt, SystemExit)):
                        caught = dumpable_exc
            target_process_started = target_process_started or (run_dir / "target_started").is_file()
            target_process_returned = target_process_returned or (run_dir / "target_returned").is_file()
            interrupted_before_cleanup = isinstance(caught, KeyboardInterrupt) or driver_exit in {
                -signal.SIGINT,
                -signal.SIGTERM,
                -signal.SIGHUP,
            }
            if interrupted_before_cleanup:
                attributable_activity = raw_attempt_has_attributable_activity(
                    condition_map(manifest)[slot["condition_id"]]["driver"], run_dir
                )
            for signum in watched_signals:
                signal.signal(signum, record_cleanup_interruption)
            if run_dir.is_dir():
                try:
                    runtime_scan_issues = credential_receipt_issues(
                        run_dir / "credential_scan.runtime.json",
                        condition_map(manifest)[slot["condition_id"]]["driver"],
                        expected_source_structure_sha256=current_preflight.get(
                            "redacted_credential_structure_sha256"
                        ),
                    )
                    if target_process_started and runtime_scan_issues:
                        raise credential_guard.CredentialGuardError(
                            "runtime credential-state scan evidence failed validation"
                        )
                    scan_run_credentials(
                        condition_map(manifest)[slot["condition_id"]]["driver"],
                        env,
                        run_dir,
                        "credential_scan.json",
                    )
                    if isinstance(caught, SecretLeakError):
                        raise caught
                    if record is not None:
                        write_artifact_manifest(
                            manifest,
                            slot,
                            run_dir,
                            record_kind="normalized_run",
                        )
                    else:
                        write_artifact_manifest(
                            manifest,
                            slot,
                            run_dir,
                            record_kind="failed_attempt",
                        )
                except BaseException as scan_exc:
                    if caught is None or not isinstance(caught, (KeyboardInterrupt, SystemExit)):
                        caught = scan_exc
                    record = None
                    try:
                        quarantine = quarantine_with_fallback(
                            manifest,
                            slot,
                            run_dir,
                            primary=quarantine_handle,
                            fallback=emergency_quarantine_handle,
                        )
                    except BaseException as quarantine_exc:
                        if caught is None or not isinstance(caught, (KeyboardInterrupt, SystemExit)):
                            caught = quarantine_exc
                        try:
                            quarantine = write_quarantine_failure(
                                manifest, slot, run_dir, quarantine_exc
                            )
                        except BaseException as receipt_exc:
                            quarantine = {
                                "succeeded": False,
                                "receipt": None,
                                "receipt_error_type": type(receipt_exc).__name__,
                            }
        if (
            synthetic_crash is not None
            or not attempt_intent_claimed
            or not launch_authorized
        ):
            for signum, prior_handler in previous_signal_handlers.items():
                signal.signal(signum, prior_handler)
            close_process_scope(process_scope)
            dispose_quarantine(emergency_quarantine_handle)
            close_quarantine(quarantine_handle)
            if synthetic_crash is not None:
                raise synthetic_crash
            if caught is not None:
                raise caught
            raise RuntimeError(
                "attempt claim failed authorization before driver process launch"
            )
        if record is not None:
            validity_state = record["validity"]["state"]
            analysis_eligible = record["validity"]["confirmatory_analysis_eligible"]
            objective_issues = record["validity"]["technical_issues"]
            eligible_reasons = eligible_exclusion_reasons(record)
            smoke_excluded = record["validity"]["smoke_excluded"]
            failure_receipt = None
        else:
            quarantine_succeeded = bool(quarantine and quarantine.get("succeeded"))
            validity_state = (
                "security_quarantined"
                if quarantine_succeeded
                else "staged_recovery_quarantined"
                if stage_quarantine and stage_quarantine.get("succeeded")
                else "security_quarantine_failed"
                if quarantine
                else "runner_or_normalization_failure"
            )
            analysis_eligible = False
            smoke_excluded = manifest["phase"] == "smoke"
            objective_issues = [
                "security quarantine after secret scan"
                if quarantine_succeeded
                else "staged driver recovery failed; external stage quarantined"
                if stage_quarantine and stage_quarantine.get("succeeded")
                else "atomic security quarantine failed; run halted for manual recovery"
                if quarantine
                else f"{type(caught).__name__ if caught else 'UnknownError'} during driver or normalization"
            ]
            eligible_reasons = ([
                "security_quarantine_after_secret_scan"
                if quarantine_succeeded
                else "corrupted_or_missing_raw_artifact_due_to_harness"
                if driver_process_spawned or target_process_started
                else "harness_crash_before_target_execution"
            ] if not quarantine or quarantine_succeeded else [])
            interrupted = isinstance(caught, KeyboardInterrupt) or driver_exit in {
                -signal.SIGINT,
                -signal.SIGTERM,
                -signal.SIGHUP,
            }
            if (
                interrupted
                and target_process_started
                and attributable_activity is False
            ):
                eligible_reasons.append(
                    "external_termination_before_attributable_target_completion"
                )
            eligible_reasons = sorted(set(eligible_reasons))
            failure_receipt = write_attempt_failure(
                manifest,
                slot,
                {
                    "schema_version": 1,
                    "experiment_id": manifest["experiment_id"],
                    "manifest_freeze_id": manifest["freeze_id"],
                    "slot_id": slot["slot_id"],
                    "started_at": started,
                    "finished_at": utc_now(),
                    "driver_exit": driver_exit,
                    "driver_process_spawned": driver_process_spawned,
                    "target_process_started": target_process_started,
                    "target_process_returned": target_process_returned,
                    "process_group_cleaned": process_group_cleaned,
                    "staged_attempt_retained": staged_attempt_retained,
                    "staged_attempt_path": (
                        os.path.abspath(attempt_root) if staged_attempt_retained else None
                    ),
                    "error_type": type(caught).__name__ if caught else "UnknownError",
                    "error_message": str(caught) if caught else "unknown driver or normalization failure",
                    "quarantine": quarantine,
                    "stage_quarantine": stage_quarantine,
                },
            )
        try:
            synthetic_crash_checkpoint(test_only_crash_checkpoint, "pre_ledger")
            append_ledger(
                ledger_path,
                {
                    "schema_version": 1,
                    "slot_id": slot["slot_id"],
                    "phase": manifest["phase"],
                    "condition_id": slot["condition_id"],
                    "kind": slot.get("kind", "primary"),
                    "replacement_for": slot.get("replacement_for"),
                    "exclusion_reason": slot.get("exclusion_reason"),
                    "run_dir": relative(run_dir),
                    "started_at": started,
                    "finished_at": utc_now(),
                    "driver_exit": driver_exit,
                    "process_group_cleaned": process_group_cleaned,
                    "staged_attempt_retained": staged_attempt_retained,
                    "staged_attempt_path": (
                        os.path.abspath(attempt_root) if staged_attempt_retained else None
                    ),
                    "validity_state": validity_state,
                    "analysis_eligible": analysis_eligible,
                    "smoke_excluded": smoke_excluded,
                    "objective_issues": objective_issues,
                    "eligible_exclusion_reasons": eligible_reasons,
                    "attempt_intent": attempt_intent_relative,
                    "attempt_intent_sha256": attempt_intent_sha256,
                    "attempt_claim_journal": (
                        attempt_claim["path"] if attempt_claim is not None else None
                    ),
                    "attempt_claim_sequence": (
                        attempt_claim["line"] if attempt_claim is not None else None
                    ),
                    "attempt_claim_sha256": (
                        attempt_claim["sha256"] if attempt_claim is not None else None
                    ),
                    "preflight": current_preflight,
                    "failure_receipt": failure_receipt,
                    "failure_receipt_sha256": sha256_path(ROOT / failure_receipt) if failure_receipt else None,
                    "quarantine_receipt": (
                        quarantine.get("receipt")
                        if quarantine and quarantine.get("succeeded") is True
                        else None
                    ),
                    "quarantine_receipt_sha256": (
                        quarantine.get("receipt_sha256")
                        if quarantine
                        and quarantine.get("succeeded") is True
                        and quarantine.get("receipt")
                        else None
                    ),
                    "quarantine_failure_receipt": (
                        quarantine.get("receipt")
                        if quarantine and quarantine.get("succeeded") is False
                        else None
                    ),
                    "quarantine_failure_receipt_sha256": (
                        quarantine.get("receipt_sha256")
                        if quarantine
                        and quarantine.get("succeeded") is False
                        and quarantine.get("receipt")
                        else None
                    ),
                    "stage_quarantine_receipt": (
                        stage_quarantine.get("receipt") if stage_quarantine else None
                    ),
                    "stage_quarantine_receipt_sha256": (
                        stage_quarantine.get("receipt_sha256")
                        if stage_quarantine and stage_quarantine.get("receipt")
                        else None
                    ),
                    "artifact_manifest_sha256": sha256_path(run_dir / "artifact_manifest.json")
                    if (run_dir / "artifact_manifest.json").is_file()
                    else None,
                    "instruction_policy_signature_sha256": (
                        record["configuration"]["instruction_policy_signature"]["sha256"]
                        if record is not None
                        else None
                    ),
                },
            )
        finally:
            for signum, prior_handler in previous_signal_handlers.items():
                signal.signal(signum, prior_handler)
            close_process_scope(process_scope)
            dispose_quarantine(emergency_quarantine_handle)
            close_quarantine(quarantine_handle)
        if cleanup_signal is not None and caught is None:
            caught = OperatorTermination(cleanup_signal)
        if caught is not None:
            if isinstance(caught, (KeyboardInterrupt, SystemExit)):
                raise caught
            raise RuntimeError(f"attempt {slot['slot_id']} failed after its ledger row was preserved") from caught
        if manifest["phase"] == "confirmatory" and analysis_eligible is False:
            raise RuntimeError(
                f"attempt {slot['slot_id']} is analysis-ineligible; run its next frozen reserve before any later primary"
            )
        if record is not None and record["validity"]["state"] == "invalid_setup":
            raise RuntimeError(f"attempt {slot['slot_id']} failed the run-integrity gate; matrix halted")


def make_blind_packets(manifest_path: Path, output_dir: Path, key: str) -> dict[str, Any]:
    manifest, _manifest_snapshot = read_manifest_strict(
        manifest_path, label="blinding manifest"
    )
    if manifest.get("phase") != "confirmatory":
        raise ValueError("smoke outputs may not enter semantic-review packets")
    if len(key.encode()) < 32 or len(set(key)) < 8:
        raise ValueError("blinding key must contain at least 32 bytes and 8 distinct characters")
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("manifest invalid: " + "; ".join(errors))
    ledger_path = ROOT / manifest["bout_dir"] / "EXECUTION.jsonl"
    ledger, _ledger_snapshot = read_execution_ledger(ledger_path)
    effective, ledger_errors = select_effective_attempts(manifest, ledger)
    ledger_errors.extend(validate_prior_attempt_provenance(manifest, ledger))
    if ledger_errors:
        raise ValueError("execution ledger cannot produce a frozen matrix: " + "; ".join(ledger_errors))
    frozen_slots = {
        slot["slot_id"]: slot for slot in [*manifest["schedule"], *(manifest.get("reserve_slots") or [])]
    }
    packets = []
    mapping = []
    observed_run_ids: set[tuple[str, str]] = set()
    for primary in manifest["schedule"]:
        attempt_row = effective[primary["slot_id"]]
        attempt_slot = frozen_slots[attempt_row["slot_id"]]
        run_dir = ROOT / attempt_row["run_dir"]
        record, provenance_errors = validate_run_provenance(manifest, attempt_slot, attempt_row)
        if provenance_errors:
            raise ValueError("effective attempt provenance failed: " + "; ".join(provenance_errors))
        assert record is not None
        if not record["validity"]["confirmatory_analysis_eligible"]:
            raise ValueError(f"ledger eligibility disagrees with run record for {attempt_row.get('slot_id')}")
        driver = record["condition"]["driver"]
        identifier_key = {"claude": "session_id", "codex": "thread_id", "kimi": "session_id"}[driver]
        identifiers = ((record.get("configuration") or {}).get("run_identifiers") or {}).get(identifier_key) or []
        if len(identifiers) != 1:
            raise ValueError(f"effective attempt lacks exactly one {identifier_key}: {attempt_row.get('slot_id')}")
        identity = (driver, identifiers[0])
        if identity in observed_run_ids:
            raise ValueError(f"duplicate emitted run/session identifier: {driver}")
        observed_run_ids.add(identity)
        text = (run_dir / "final_output.txt").read_text()
        blind_id = "P-" + hmac.new(key.encode(), primary["slot_id"].encode(), hashlib.sha256).hexdigest()[:16]
        packets.append({"blind_id": blind_id, "output_sha256": sha256_bytes(text.encode()), "output": text})
        mapping.append(
            {
                "blind_id": blind_id,
                "primary_slot_id": primary["slot_id"],
                "attempt_slot_id": attempt_row["slot_id"],
                "condition_id": primary["condition_id"],
                "run_dir": relative(run_dir),
                "output_sha256": sha256_bytes(text.encode()),
            }
        )
    # HMAC-derived order prevents the public randomized schedule from revealing
    # condition labels by packet position. The custodian mapping stays withheld.
    packets.sort(key=lambda packet: packet["blind_id"])
    mapping.sort(key=lambda item: item["blind_id"])
    output_dir.mkdir(parents=True, exist_ok=False)
    review_dir = output_dir / "reviewer"
    custodian_dir = output_dir / "custodian"
    review_dir.mkdir(mode=0o755)
    custodian_dir.mkdir(mode=0o700)
    common = {"schema_version": 1, "experiment_id": manifest["experiment_id"], "manifest_freeze_id": manifest["freeze_id"]}
    write_json(review_dir / "review-packets.json", {**common, "packets": packets})
    map_path = custodian_dir / "blind-map.json"
    write_json(map_path, {**common, "mapping": mapping})
    map_path.chmod(0o600)
    return {"packets": packets, "mapping": mapping}


def _find_slot(manifest: dict[str, Any], slot_id: str) -> dict[str, Any]:
    for slot in manifest.get("schedule") or []:
        if slot.get("slot_id") == slot_id:
            return slot
    raise ValueError(f"slot not found: {slot_id}")


def technical_smoke_status(manifest_path: Path, *, historical: bool = False) -> dict[str, Any]:
    """Return a response-free technical view of one excluded-smoke ledger."""
    manifest, _manifest_snapshot = read_manifest_strict(
        manifest_path, label="smoke-status manifest"
    )
    if manifest.get("phase") != "smoke":
        raise ValueError("technical smoke status accepts only a smoke manifest")
    manifest_errors = validate_manifest(
        manifest,
        check_files=not historical,
        allow_historical=historical,
    )
    if manifest_errors:
        raise ValueError("smoke manifest is invalid: " + "; ".join(manifest_errors))
    historical_commit: str | None = None
    if historical:
        historical_commit, historical_errors = validate_historical_smoke_sources(
            manifest_path,
            manifest,
        )
        if historical_errors:
            raise ValueError(
                "historical smoke source verification failed: "
                + "; ".join(historical_errors)
            )
    ledger_path = ROOT / str(manifest.get("bout_dir", "")) / "EXECUTION.jsonl"
    ledger, _ledger_snapshot = read_execution_ledger(ledger_path)
    ledger_errors = validate_execution_ledger(manifest, ledger)
    ledger_errors.extend(validate_prior_attempt_provenance(manifest, ledger))
    if ledger_errors:
        raise ValueError("smoke artifact integrity failed: " + "; ".join(ledger_errors))
    runs: list[dict[str, Any]] = []
    for row in ledger:
        run_dir = ROOT / str(row["run_dir"])
        record = load_json(run_dir / "run_record.json")
        metrics = load_json(run_dir / "metrics.json")
        condition = condition_map(manifest)[row["condition_id"]]
        completion = record.get("completion") or {}
        embargo = record.get("embargo") or {}
        output = record.get("output") or {}
        identity = ((record.get("configuration") or {}).get("observed_identity") or {})
        policy = ((record.get("configuration") or {}).get("instruction_policy_signature") or {})
        runs.append(
            {
                "slot_id": row["slot_id"],
                "condition_id": row["condition_id"],
                "driver": condition["driver"],
                "requested_model": condition["requested_model"],
                "observed_identity": {
                    key: identity.get(key)
                    for key in ("models", "model_aliases", "providers")
                    if key in identity
                },
                "driver_exit": row.get("driver_exit"),
                "validity_state": row.get("validity_state"),
                "analysis_eligible": row.get("analysis_eligible"),
                "smoke_excluded": row.get("smoke_excluded"),
                "process_group_cleaned": row.get("process_group_cleaned"),
                "staged_attempt_retained": row.get("staged_attempt_retained"),
                "eligible_exclusion_reasons": row.get("eligible_exclusion_reasons") or [],
                "artifact_manifest_sha256": row.get("artifact_manifest_sha256"),
                "instruction_policy_signature_sha256": policy.get("sha256"),
                "completion": {
                    key: completion.get(key)
                    for key in (
                        "agent_exit",
                        "timeout_exit",
                        "output_present",
                        "request_acceptance_observed",
                        "pre_request_transport_failure_observed",
                        "target_response_activity_observed",
                        "truncation_observed",
                    )
                },
                "output": {
                    "present": output.get("present"),
                    "bytes": output.get("bytes"),
                    "sha256": output.get("sha256"),
                },
                "embargo": {
                    key: embargo.get(key)
                    for key in (
                        "pass",
                        "trace_integrity_pass",
                        "trace_integrity_failure",
                        "target_originated_tool_or_function_call",
                        "spawned_agent",
                        "repository_or_file_inspection",
                        "research_or_network_action",
                        "implementation_or_mutation_attempt",
                        "unclassified_tool_action",
                        "workspace_changed",
                    )
                },
                "tool_event_count": embargo.get("tool_call_count"),
                "unknown_trace_shape_count": len(embargo.get("trace_unknowns") or []),
                "technical_issue_count": len((record.get("validity") or {}).get("technical_issues") or []),
                "metrics": {
                    key: metrics.get(key)
                    for key in (
                        "wall_seconds",
                        "input_tokens",
                        "cached_input_tokens",
                        "output_tokens",
                        "reasoning_output_tokens",
                        "total_cost_usd",
                    )
                    if key in metrics
                },
            }
        )
    return {
        "schema_version": 1,
        "experiment_id": manifest["experiment_id"],
        "manifest_freeze_id": manifest["freeze_id"],
        "phase": "smoke",
        "historical_current_worktree_source_check_skipped": historical,
        "historical_git_frozen_source_check_pass": True if historical else None,
        "historical_frozen_sources_verified_at_commit": historical_commit,
        "response_and_instruction_content_omitted": True,
        "attempt_count": len(runs),
        "runs": runs,
    }


def command_manifest(args: argparse.Namespace) -> None:
    smoke_replacement_from = getattr(args, "smoke_replacement_from", None)
    manifest = build_manifest(
        phase=args.phase,
        output=_lexical_absolute_path(Path(args.output)),
        design=Path(args.design).resolve(),
        analysis_script=Path(args.analysis_script).resolve(),
        report_template=Path(args.report_template).resolve(),
        repeats=args.runs,
        seed=args.seed,
        frozen_at=args.frozen_at,
        reserve_per_condition=args.reserves,
        replace_draft=args.replace_draft,
        bout_dir_override=args.bout_dir,
        smoke_continuation_from=(
            _lexical_absolute_path(Path(args.smoke_continuation_from))
            if args.smoke_continuation_from
            else None
        ),
        smoke_replacement_from=(
            _lexical_absolute_path(Path(smoke_replacement_from))
            if smoke_replacement_from
            else None
        ),
    )
    print(manifest["freeze_id"])


def command_validate(args: argparse.Namespace) -> None:
    manifest, _manifest_snapshot = read_manifest_strict(
        Path(args.manifest), label="validation manifest"
    )
    errors = validate_manifest(manifest, check_files=not args.no_file_check)
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        raise SystemExit(1)
    print(f"valid {manifest['phase']} manifest: {manifest['freeze_id']}")


def command_preflight(args: argparse.Namespace) -> None:
    manifest, _manifest_snapshot = read_manifest_strict(
        Path(args.manifest), label="preflight manifest"
    )
    snapshots = preflight_manifest(manifest, set(condition_map(manifest)), dict(os.environ))
    print(json.dumps({"manifest_freeze_id": manifest["freeze_id"], "conditions": snapshots}, indent=2))


def command_observe(args: argparse.Namespace) -> None:
    manifest, _manifest_snapshot = read_manifest_strict(
        Path(args.manifest), label="observation manifest"
    )
    slot = _find_slot(manifest, args.slot)
    record = observe_run(manifest, slot, output_dir_for(manifest, slot))
    print(json.dumps(record["validity"], indent=2))


def command_verify(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir).resolve()
    errors = verify_artifacts(run_dir)
    historical_commit: str | None = None
    manifest_path = next(
        (parent / "MANIFEST.json" for parent in run_dir.parents if (parent / "MANIFEST.json").is_file()),
        None,
    )
    if manifest_path is None:
        errors.append("no enclosing frozen MANIFEST.json found")
    else:
        manifest, _manifest_snapshot = read_manifest_strict(
            manifest_path, label="artifact-verification manifest"
        )
        errors.extend(
            validate_manifest(
                manifest,
                check_files=not args.historical,
                allow_historical=args.historical,
            )
        )
        if args.historical:
            historical_commit, historical_errors = validate_historical_smoke_sources(
                manifest_path,
                manifest,
            )
            errors.extend(historical_errors)
        ledger_path = manifest_path.parent / "EXECUTION.jsonl"
        try:
            ledger, _ledger_snapshot = read_execution_ledger(ledger_path)
        except (OSError, ValueError) as exc:
            ledger = []
            errors.append(
                f"execution ledger is unsafe or malformed: {type(exc).__name__}: {exc}"
            )
        errors.extend(validate_execution_ledger(manifest, ledger))
        try:
            run_rel = relative(run_dir)
        except ValueError:
            run_rel = ""
        rows = [row for row in ledger if row.get("run_dir") == run_rel]
        if len(rows) != 1:
            errors.append("run directory is not anchored exactly once in the execution ledger")
        else:
            slots = {
                slot["slot_id"]: slot
                for slot in [*(manifest.get("schedule") or []), *(manifest.get("reserve_slots") or [])]
            }
            slot = slots.get(rows[0].get("slot_id"))
            if slot is None:
                errors.append("execution ledger row does not reference a frozen slot")
            else:
                _, record_kind, anchor_errors = validate_artifact_anchor(manifest, slot, rows[0])
                if record_kind == "normalized_run":
                    _, provenance_errors = validate_run_provenance(manifest, slot, rows[0])
                else:
                    provenance_errors = anchor_errors
                    if record_kind == "failed_attempt" and rows[0].get("analysis_eligible") is not False:
                        provenance_errors.append("failed-attempt artifacts cannot be analysis eligible")
                errors.extend(provenance_errors)
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        raise SystemExit(1)
    if args.historical:
        print(
            "historical artifact and frozen-source integrity: OK at Git commit "
            + str(historical_commit)
        )
    else:
        print("artifact integrity: OK")


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__)
    sub = cli.add_subparsers(dest="command", required=True)
    manifest = sub.add_parser("manifest", help="construct a frozen randomized manifest")
    manifest.add_argument("--phase", choices=("smoke", "confirmatory"), required=True)
    manifest.add_argument("--output", required=True)
    manifest.add_argument("--design", required=True)
    manifest.add_argument("--analysis-script", required=True)
    manifest.add_argument("--report-template", required=True)
    manifest.add_argument("--runs", type=int, required=True)
    manifest.add_argument("--reserves", type=int, default=5)
    manifest.add_argument("--seed", type=int, required=True)
    manifest.add_argument("--frozen-at", required=True)
    manifest.add_argument(
        "--bout-dir",
        help="repository-relative artifact directory; defaults to the phase's canonical base path",
    )
    manifest.add_argument(
        "--smoke-continuation-from",
        help="derive only the unattempted suffix of the immutable initial smoke manifest",
    )
    manifest.add_argument(
        "--smoke-replacement-from",
        help="construct the one-slot Amendment-5 Kimi replacement from the frozen Amendment-4 smoke manifest",
    )
    manifest.add_argument(
        "--replace-draft",
        action="store_true",
        help="replace only a same-experiment draft that has no run artifacts or execution ledger",
    )
    manifest.set_defaults(func=command_manifest)
    validate = sub.add_parser("validate", help="validate a frozen manifest and its inputs")
    validate.add_argument("manifest")
    validate.add_argument("--no-file-check", action="store_true")
    validate.set_defaults(func=command_validate)
    preflight = sub.add_parser("preflight", help="run every no-API treatment gate")
    preflight.add_argument("manifest")
    preflight.set_defaults(func=command_preflight)
    run = sub.add_parser("run", help="execute manifest slots serially")
    run.add_argument("manifest")
    run.add_argument("--approval")
    run.add_argument("--slot", action="append", dest="slots")
    run.add_argument("--reserve", dest="reserve_slot")
    run.add_argument("--replacement-for")
    run.add_argument("--exclusion-reason")
    run.add_argument("--dry-run", action="store_true")
    run.set_defaults(
        func=lambda args: run_slots(
            Path(args.manifest),
            approval=args.approval,
            requested_slots=set(args.slots) if args.slots else None,
            dry_run=args.dry_run,
            reserve_slot=args.reserve_slot,
            replacement_for=args.replacement_for,
            exclusion_reason=args.exclusion_reason,
        )
    )
    observe = sub.add_parser("observe", help="regenerate normalized evidence for one run")
    observe.add_argument("manifest")
    observe.add_argument("--slot", required=True)
    observe.set_defaults(func=command_observe)
    verify = sub.add_parser("verify-run", help="verify a run's content-addressed artifacts")
    verify.add_argument("run_dir")
    verify.add_argument(
        "--historical",
        action="store_true",
        help="verify an immutable superseded run while allowing its frozen source tree to have advanced",
    )
    verify.set_defaults(func=command_verify)
    smoke_status = sub.add_parser(
        "smoke-status",
        help="emit a response-free technical view of an excluded-smoke ledger",
    )
    smoke_status.add_argument("manifest")
    smoke_status.add_argument(
        "--historical",
        action="store_true",
        help="allow source-tree drift for a superseded immutable smoke manifest",
    )
    smoke_status.set_defaults(
        func=lambda args: print(
            json.dumps(
                technical_smoke_status(Path(args.manifest), historical=args.historical),
                indent=2,
            )
        )
    )
    blind = sub.add_parser("blind", help="create label-free semantic-review packets")
    blind.add_argument("manifest")
    blind.add_argument("--output-dir", required=True)
    blind.add_argument("--key-env", default="ARENA_BLIND_KEY")
    blind.set_defaults(
        func=lambda args: print(
            json.dumps(
                {
                    "packet_count": len(
                        make_blind_packets(
                            Path(args.manifest),
                            Path(args.output_dir),
                            os.environ.get(args.key_env)
                            or (_ for _ in ()).throw(ValueError(f"missing blinding key in {args.key_env}")),
                        )["packets"]
                    )
                }
            )
        )
    )
    return cli


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    try:
        args.func(args)
    except (FileExistsError, PermissionError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
