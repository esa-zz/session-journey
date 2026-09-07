#!/usr/bin/env python3
"""Create and append to minimal session journey files.

The script owns mechanics only: UUID/session path creation, session fingerprints,
event IDs, UTC timestamps, references, validation, locking, and append-only writes.
It does not summarize sessions or manage task state.

Every command raises ValueError for bad input and OSError for I/O trouble.
main() turns both into one "error: ..." line on stderr and exit code 2.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import errno
import hashlib
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Iterator, TextIO

# --- File format -----------------------------------------------------------

FINGERPRINT_DOMAIN = b"session-journey:v1\0"
EVENT_TAG_HEX_LENGTH = 20  # first hex chars of the fingerprint used in event IDs
SEQUENCE_MIN_DIGITS = 4  # 0001, 0002, ... 9999, 10000
FIRST_SEQUENCE = 1

UUID_PATTERN = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
KIND_PATTERN = r"[a-z][a-z0-9-]{0,31}"
EVENT_ID_PATTERN = rf"J[0-9a-f]{{{EVENT_TAG_HEX_LENGTH}}}-[0-9]+"

KIND_RE = re.compile(KIND_PATTERN)
EVENT_ID_RE = re.compile(rf"J([0-9a-f]{{{EVENT_TAG_HEX_LENGTH}}})-([0-9]+)")

# A well-formed event heading line, e.g. "## Jf98641ad65550efc32bc-0003 · pivot".
EVENT_HEADING_RE = re.compile(rf"## ({EVENT_ID_PATTERN}) · {KIND_PATTERN}\s*")
# Anything in our reserved event-ID namespace. Rejected inside bodies,
# and must be well formed when it appears in a journey file.
EVENT_HEADING_LIKE_RE = re.compile(rf"^## J[0-9A-Fa-f]{{{EVENT_TAG_HEX_LENGTH}}}-", re.MULTILINE)

# Last five path parts: sessions/<YYYY>/<MM>/<DD>/<HHMMSS>Z_<uuid>.md
CANONICAL_PATH_TAIL_RE = re.compile(
    rf"sessions/(\d{{4}})/(\d{{2}})/(\d{{2}})/(\d{{2}})(\d{{2}})(\d{{2}})Z_({UUID_PATTERN})\.md"
)
CANONICAL_PATH_DEPTH = 5

CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")

START_LOCK_NAME = ".session-journey-start.lock"
LOCK_REGION_BYTES = 1  # Windows locks a byte range; one byte at offset 0 is enough


# --- Time and identifiers --------------------------------------------------


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def format_utc(value: dt.datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def canonical_uuid(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise ValueError(f"invalid UUID: {value}") from exc


def session_fingerprint(session_id: str, started_at: str) -> str:
    payload = FINGERPRINT_DOMAIN + session_id.encode("ascii") + b"\0" + started_at.encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def event_tag(fingerprint: str) -> str:
    return fingerprint[:EVENT_TAG_HEX_LENGTH]


def make_event_id(tag: str, number: int) -> str:
    return f"J{tag}-{number:0{SEQUENCE_MIN_DIGITS}d}"


def check_event_id(value: str) -> None:
    """Reject anything that is not a canonical event ID such as J<20 hex>-0003."""
    match = EVENT_ID_RE.fullmatch(value)
    if match is None:
        raise ValueError(f"invalid journey ref: {value}; expected J<20-lowercase-hex>-<sequence>")
    tag, sequence = match.groups()
    number = int(sequence)
    if number < FIRST_SEQUENCE or value != make_event_id(tag, number):
        raise ValueError(f"non-canonical journey ref: {value}")


# --- Paths -----------------------------------------------------------------


def journey_path_for(sessions_root: Path, session_id: str, started: dt.datetime) -> Path:
    day_dir = sessions_root / started.strftime("%Y") / started.strftime("%m") / started.strftime("%d")
    return day_dir / f"{started.strftime('%H%M%S')}Z_{session_id}.md"


def identity_from_path(path: Path) -> tuple[str, str]:
    """Return (session_id, started_at) encoded in a canonical journey path."""
    tail = "/".join(path.parts[-CANONICAL_PATH_DEPTH:])
    match = CANONICAL_PATH_TAIL_RE.fullmatch(tail)
    if match is None:
        raise ValueError(f"journey path is not canonical: {path}")
    *time_parts, session_id = match.groups()
    try:
        started = dt.datetime(*map(int, time_parts), tzinfo=dt.timezone.utc)
    except ValueError as exc:
        raise ValueError(f"journey path contains an invalid UTC date/time: {path}") from exc
    return session_id, format_utc(started)


def find_existing_journey(sessions_root: Path, session_id: str) -> Path | None:
    matches = [path for path in sessions_root.rglob(f"*_{session_id}.md") if path.is_file()]
    for path in matches:
        identity_from_path(path)  # raises if a journey-like file uses a non-canonical path
    if len(matches) > 1:
        raise ValueError(f"multiple journeys exist for session UUID {session_id}")
    return matches[0] if matches else None


# --- Locking ---------------------------------------------------------------

if os.name == "nt":
    import msvcrt

    # msvcrt.locking(LK_LOCK) gives up after roughly ten seconds with one of
    # these errors. Retrying keeps Windows blocking like the POSIX path.
    LOCK_CONTENTION_ERRNOS = {errno.EACCES, getattr(errno, "EDEADLOCK", errno.EDEADLK)}

    @contextlib.contextmanager
    def exclusive_lock(handle: TextIO) -> Iterator[None]:
        handle.seek(0)
        while True:
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, LOCK_REGION_BYTES)
                break
            except OSError as exc:
                if exc.errno not in LOCK_CONTENTION_ERRNOS:
                    raise
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, LOCK_REGION_BYTES)

else:
    import fcntl

    @contextlib.contextmanager
    def exclusive_lock(handle: TextIO) -> Iterator[None]:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def session_start_lock(memory_root: Path) -> Iterator[None]:
    """Serialize lookup + creation of a session journey within one memory root."""
    memory_root.mkdir(parents=True, exist_ok=True)
    # Zero-byte operational file, not session memory.
    with (memory_root / START_LOCK_NAME).open("a+", encoding="utf-8", newline="") as handle:
        with exclusive_lock(handle):
            yield


# --- Journey content -------------------------------------------------------


def session_header(session_id: str, started_at: str) -> str:
    fingerprint = session_fingerprint(session_id, started_at)
    return (
        "# Session journey\n\n"
        f"Session: `{session_id}`\n"
        f"Started: `{started_at}`\n"
        f"Session-Fingerprint: `sha256:{fingerprint}`\n\n"
        "This file is append-only. Correct or supersede earlier entries with a new event.\n"
    )


def markdown_code_span(value: str) -> str:
    """Render one single-line value as a CommonMark-safe inline code span."""
    longest_backtick_run = max((len(run) for run in re.findall(r"`+", value)), default=0)
    fence = "`" * (longest_backtick_run + 1)
    pad = " " if value.startswith("`") or value.endswith("`") else ""
    return f"{fence}{pad}{value}{pad}{fence}"


def render_event(event_id: str, kind: str, timestamp: str, refs: list[str], external_refs: list[str], body: str) -> str:
    lines = ["", f"## {event_id} · {kind}", "", f"Time: {markdown_code_span(timestamp)}"]
    if refs:
        lines.append("Refs: " + ", ".join(map(markdown_code_span, refs)))
    if external_refs:
        lines.append("External refs: " + ", ".join(map(markdown_code_span, external_refs)))
    lines += ["", body, ""]
    return "\n".join(lines)


def event_ids_in(content: str) -> list[str]:
    """Return every event ID in file order. Raise on a heading that is almost, but not quite, valid."""
    ids = []
    for line in content.splitlines():
        if not EVENT_HEADING_LIKE_RE.match(line):
            continue
        match = EVENT_HEADING_RE.fullmatch(line)
        if match is None:
            raise ValueError(f"journey contains a malformed event heading: {line!r}")
        ids.append(match.group(1))
    return ids


def validate_journey(content: str, path: Path) -> tuple[str, list[str]]:
    """Check header and event IDs against the path. Return (event tag, event IDs)."""
    session_id, started_at = identity_from_path(path)
    if not content.startswith(session_header(session_id, started_at)):
        raise ValueError(f"journey header does not match its canonical path (Session, Started, or Session-Fingerprint): {path}")

    tag = event_tag(session_fingerprint(session_id, started_at))
    event_ids = event_ids_in(content)
    for number, event_id in enumerate(event_ids, start=FIRST_SEQUENCE):
        if event_id != make_event_id(tag, number):
            raise ValueError(
                f"unexpected event ID {event_id}; expected {make_event_id(tag, number)} "
                "(IDs must use the session fingerprint and a contiguous sequence from 0001)"
            )
    return tag, event_ids


# --- Input validation ------------------------------------------------------


def read_body(args: argparse.Namespace) -> str:
    if args.text is not None:
        body = args.text
    elif args.body_file is not None:
        body = Path(args.body_file).expanduser().read_text(encoding="utf-8")
    elif sys.stdin.isatty():
        raise ValueError("event body required: pipe stdin, use --text, or use --body-file")
    else:
        body = sys.stdin.read()

    # The stored contract is LF-only regardless of where the text came from.
    body = body.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not body:
        raise ValueError("event body must not be empty")
    if EVENT_HEADING_LIKE_RE.search(body):
        raise ValueError("event body must not contain a journey event heading such as '## J0123456789abcdefabcd-0001 · kind'")
    return body


def check_kind(kind: str) -> None:
    if not KIND_RE.fullmatch(kind):
        raise ValueError("--kind must be a lowercase slug such as discovery, decision, or pivot")


def check_external_ref(ref: str) -> None:
    single_clean_line = ref and ref == ref.strip() and not CONTROL_CHAR_RE.search(ref)
    if not single_clean_line:
        raise ValueError("each --external-ref must be a trimmed, non-empty single line without control characters")


def unique(values: list[str] | None) -> list[str]:
    return list(dict.fromkeys(values or []))


# --- Commands --------------------------------------------------------------


def cmd_start(args: argparse.Namespace) -> int:
    session_id = canonical_uuid(args.session_id) if args.session_id else str(uuid.uuid4())
    project_root = Path(args.project_root).expanduser().resolve()
    memory_root = project_root / Path(args.memory_dir).expanduser()  # absolute memory_dir wins
    sessions_root = memory_root / "sessions"

    with session_start_lock(memory_root):
        existing = find_existing_journey(sessions_root, session_id)
        if existing is not None:
            raise ValueError(f"session already exists: {existing}")

        started = utc_now()
        journey_path = journey_path_for(sessions_root, session_id, started)
        journey_path.parent.mkdir(parents=True, exist_ok=True)
        with journey_path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(session_header(session_id, format_utc(started)))
            handle.flush()
            os.fsync(handle.fileno())

    shown_path = journey_path.relative_to(project_root) if journey_path.is_relative_to(project_root) else journey_path
    print(f"session {session_id}")
    print(f"journey {shown_path}")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    journey_path = Path(args.journey).expanduser().resolve()
    if not journey_path.is_file():
        raise ValueError(f"journey does not exist: {journey_path}")

    check_kind(args.kind)
    body = read_body(args)
    refs = unique(args.ref)
    for ref in refs:
        check_event_id(ref)
    external_refs = unique(args.external_ref)
    for ref in external_refs:
        check_external_ref(ref)

    # r+ never truncates. Validation and the append happen under one lock so
    # concurrent appenders cannot allocate the same sequential ID.
    with journey_path.open("r+", encoding="utf-8", newline="") as handle, exclusive_lock(handle):
        content = handle.read()
        tag, event_ids = validate_journey(content, journey_path)

        unknown_refs = [ref for ref in refs if ref not in event_ids]
        if unknown_refs:
            raise ValueError("unknown or foreign-session journey ref(s): " + ", ".join(unknown_refs))

        event_id = make_event_id(tag, len(event_ids) + 1)
        event = render_event(event_id, args.kind, format_utc(utc_now()), refs, external_refs, body)

        handle.seek(0, os.SEEK_END)
        if not content.endswith("\n"):
            handle.write("\n")
        handle.write(event)
        handle.flush()
        os.fsync(handle.fileno())

    print(event_id)
    return 0


# --- CLI -------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="journey.py", description="Create and append to minimal session journey memory.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="create a new append-only session journey")
    start.add_argument("--project-root", default=".", help="project root; defaults to current directory")
    start.add_argument("--memory-dir", default=".memory", help="memory directory relative to project root; defaults to .memory")
    start.add_argument("--session-id", help="stable session UUID from the host; generates UUIDv4 when omitted")
    start.set_defaults(func=cmd_start)

    add = subparsers.add_parser("add", help="append one event; existing bytes are never rewritten")
    add.add_argument("journey", help="path to the session journey Markdown file")
    add.add_argument("--kind", required=True, help="lowercase event kind, for example discovery or pivot")
    add.add_argument("--ref", action="append", help="existing journey event ID, for example J0123456789abcdefabcd-0003; repeatable")
    add.add_argument("--external-ref", action="append", help="opaque external reference such as beads:bd-a13f or github:org/repo#42; repeatable")
    body = add.add_mutually_exclusive_group()
    body.add_argument("--text", help="event body as one argument")
    body.add_argument("--body-file", help="read event body from a UTF-8 file")
    add.set_defaults(func=cmd_add)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except (OSError, ValueError) as exc:
        # Expected input and I/O failures. Programmer errors keep their traceback.
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
