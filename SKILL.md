---
name: session-journey
description: Preserve minimal append-only episodic memory for a substantive agent session. Use when a session may survive context compaction, handoff, or restart, and when a discovery, decision, meaningful plan, failed approach, pivot, correction, blocker, or unresolved question would be expensive to rediscover. Do not use it for transcripts, routine progress, TODO tracking, or task state.
---

# Session journey

Keep a small record of the parts of a session that would matter after the conversation is gone.

A journey is not a transcript and not a task tracker. It records changes in understanding: what we learned, what we chose, what we intended but did not do, what failed, what changed direction, and what remains important to understand later.

## Storage

Use one file per session, sharded by the session start date in UTC:

```text
.memory/sessions/YYYY/MM/DD/HHMMSSZ_<uuid>.md
```

Example:

```text
.memory/sessions/2026/09/06/193015Z_5314a246-e6c3-48b9-8f7b-23ec5b4abff6.md
```

The date and time come from the same UTC instant written as `Started:` in the file. The UUID is the session identity; the pathname is storage organization only. Do not rename a journey file after creation. The helper rejects journey files that do not use this canonical path shape.

Each journey header also stores a deterministic full SHA-256 session fingerprint derived from the canonical session UUID and canonical `Started:` timestamp. The helper owns this value; agents should not calculate or edit it manually. The v1 fingerprint input is the ASCII byte sequence `session-journey:v1\0<uuid>\0<started>`. When known, the header may also record coding tool and configured agent name as lowercase slugs, for example `Tool: codex` and `Agent: default`. These fields do not affect the fingerprint or event IDs.

Event IDs are session-qualified and sequential:

```text
J<first-20-hex-of-session-fingerprint>-<sequence>
```

The sequence starts at `0001`, uses at least four decimal digits, and has no redundant leading zeros after `9999`. Example: `Jf98641ad65550efc32bc-0003`. The 20-hex prefix is an 80-bit compact namespace derived from the full 256-bit fingerprint stored in the header; it is chosen for compactness, not as a security boundary. Given a session UUID, its canonical `Started:` timestamp, and an event ID, the fingerprint prefix can be recomputed to check whether the ID belongs to that session namespace. This is an integrity/consistency check, not authentication. The helper verifies that every event ID belongs to the file's session fingerprint and that IDs are contiguous and canonical.

The helper may create `.memory/.session-journey-start.lock` to serialize concurrent creation of the same stable session UUID. It is zero-byte operational state, not memory; agents should not read, edit, or reference it.

Create it lazily. A trivial session needs no journey. Start one when the first memory-worthy event occurs or when the work is likely to cross a context boundary.

Use the helper in `scripts/journey.py`. Do not edit, delete, reorder, or manually renumber an existing journey entry. Do not edit `Session`, `Started`, `Tool`, `Agent`, or `Session-Fingerprint`. Event IDs remain stable only while the file stays append-only.

If the host exposes a stable UUID for the current session, pass it to `start`. Otherwise let the helper generate one.

The helper requires Python >= 3.10 and has no shell dependency. Use a Python 3.10+ launcher available on the host: commonly `python3` on macOS/Linux, and `py -3` or `python` on Windows. In commands below, `<python>` means that launcher. Do not assume Bash, PowerShell, or any other specific shell.

```text
<python> <skill-root>/scripts/journey.py start --project-root . --tool <tool-slug> [--agent-name <agent-slug>]
```

Pass the current coding tool when known, such as `codex`, `claude-code`, `cline`, or `antigravity`. Tool-only start records agent `default`; pass `--agent-name` when the configured agent has another name. If tool identity is unavailable, omit both metadata options.

Keep the returned path for this session. Do not guess that the newest journey belongs to you. Concurrent sessions may exist.

## What belongs here

Append an event when forgetting it could cause a later agent to repeat a costly dead end, misunderstand an important fact, mistake an intention for an action, miss a changed constraint, or lose the reason for a direction change.

Common kinds:

- `discovery`: a fact or result that changed the working understanding
- `decision`: a choice that matters later, with the reason that makes it understandable
- `plan`: an intended action worth preserving; say clearly when it is not executed
- `failure`: an approach that was tried and failed in a way worth avoiding later
- `pivot`: a meaningful change of direction; reference the entry it replaces when possible
- `correction`: an earlier journey entry was wrong or became outdated; reference it instead of rewriting it
- `blocker`: a condition that prevents or constrains meaningful work
- `question`: an unresolved question whose answer affects future work

Kinds are labels, not a schema. The helper accepts other lowercase kinds when one is clearer. Do not invent fine-grained kinds just to classify routine activity.

## What does not belong here

Do not record:

- chat transcripts, chain-of-thought, tool traces, or command history
- files merely opened or searched
- ordinary test/build/lint output
- routine progress such as "implemented X" or "finished step 3"
- TODO lists, priorities, dependencies, ownership, task status, or ready-work queues
- facts that are obvious and cheap to recover from the current code
- long-lived project knowledge that already has a canonical home in docs, ADRs, tests, types, lint rules, or CI

Session memory should stay small enough that a future agent can read the whole journey when it is relevant.

## Task systems stay separate

A task may span many sessions, and a session may touch many tasks. Do not make the journey the source of truth for task state.

If the project uses Beads, GitHub Issues, Linear, ClickUp, or another task system, keep status, priority, dependencies, ownership, acceptance criteria, and completion state there. A journey entry may carry opaque external references so a future agent can follow them without duplicating their state.

Examples:

```text
beads:bd-a13f
github:org/repo#42
linear:ENG-318
https://tracker.example/tasks/991
```

The session-journey skill never requires an external task system and never treats external refs as task state. If the project uses Beads, read `references/guide-if-you-use-beads.md` before combining journey entries with Beads work. That guide defines the boundary between episodic session memory and Beads task/project memory.

## Append an event

Pass the journey path returned by `start`.

```text
<python> <skill-root>/scripts/journey.py add <journey-path> --kind pivot --ref <existing-journey-event-id> --external-ref beads:bd-a13f --text "The direct-push release plan is abandoned because main has no bypass actor. New direction: design a PR-based version update."
```

The helper owns the session fingerprint, event ID, UTC timestamp, append operation, and structural validation. It refuses to overwrite a journey, append to a noncanonical journey path, accept a noncanonical or foreign-session `--ref`, or reference a missing journey event.

Use multiple `--ref` or `--external-ref` arguments when needed. For a multiline body or text containing shell-sensitive characters, write the body to a UTF-8 temporary file using the host's normal file-writing mechanism and pass `--body-file <path>`. The temporary body file is input, not memory, and may be removed after the append succeeds. Prefer this over shell-specific heredocs or quoting tricks.

## Write entries for retrieval, not narration

State the durable point first. Add only the evidence and reason needed to understand it later.

For a plan, distinguish intent from action:

```text
Status: NOT EXECUTED.
```

For a failed or abandoned approach, state why it failed. For a correction or pivot, reference the earlier event. Do not clean up old entries after the fact. History is allowed to contain wrong beliefs as long as later entries correct them.

## Before a context boundary

Before a handoff, compaction, or intentional session end, scan the recent work once. Append only missing memory-worthy events. Do not add a generic session summary just because the session is ending.

If current task state matters, update the project's task system separately. That step is outside this skill.

## Example

Read `references/example-journey.md` when you need examples of the supported event patterns or the expected file shape. Do not load it just to perform a straightforward append.
