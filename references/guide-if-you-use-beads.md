# Using session-journey with Beads

Read this reference only when the project uses Beads (`bd`). Beads is optional. `session-journey` must continue to work unchanged when Beads is absent.

## Authority boundary

Keep the two systems authoritative for different things:

- **Beads owns actionable work state:** issue status, priority, dependencies, ownership, acceptance criteria, ready/blocked state, subtasks, discovered work, and completion.
- **Session journey owns episodic session memory:** discoveries, decisions, meaningful plans, failed approaches, pivots, corrections, blockers as understood during the session, and unresolved questions worth remembering.

Do not mirror Beads fields into the journey file. Do not use journey entries as TODOs.

A task may span many sessions. A session may touch many Beads. Never assume one session maps to one Bead.

## Link with external refs

When a memory-worthy event relates to a Bead, attach its stable ID as an opaque external reference:

```text
beads:bd-a13f
```

For example:

```text
<python> <skill-root>/scripts/journey.py add <journey-path> --kind discovery --external-ref beads:bd-a13f --text "The release failure occurs after deploy when release automation attempts a direct push to protected main."
```

The journey does not interpret the Bead. The reference provides provenance and a retrieval key only.

Use multiple Beads refs when one event connects existing work and newly discovered work:

```text
External refs: `beads:bd-a13f`, `beads:bd-f821`
```

Do not add a reverse link or Beads comment merely because a journey entry exists. Add one only when the task itself needs that information to be executed or handed off.

## Keep task state in Beads

Do not write entries like this:

```text
Task bd-a13f is in progress.
Priority: P1.
Remaining:
- update workflow
- add test
```

That is Beads state and will drift if copied.

A valid journey entry explains what changed in understanding:

```text
External refs: `beads:bd-a13f`

The deploy step succeeds. The failure is in post-deploy release automation, where a generated version commit is pushed directly to protected main.
```

If the project uses Beads as its task tracker, use Beads for task-state changes rather than creating Markdown TODOs or encoding those changes in the journey.

## When a discovery becomes actionable work

A journey discovery and a Beads issue are different artifacts and may both be warranted.

Example:

1. While working on `bd-a13f`, discover that release smoke tests never exercise the post-deploy release stage.
2. Append the discovery to the session journey with `beads:bd-a13f`.
3. If fixing the missing coverage is actionable work, create a Bead for it and link it with Beads' `discovered-from` dependency.
4. If useful, reference both Beads from the same or a later journey event.

Typical Beads command:

```text
bd create "Add release-stage smoke coverage" --description "The current smoke test stops before post-deploy release automation." --deps discovered-from:bd-a13f --json
```

The newly created Bead owns the work. The journey owns the fact that the work was discovered in this session and why it matters.

## Switching tasks inside one session

Do not close, rewrite, or split a journey merely because the agent changes Beads.

A single session may contain:

```text
J0123456789abcdefabcd-0001 -> beads:bd-a13f
J0123456789abcdefabcd-0002 -> beads:bd-a13f
J0123456789abcdefabcd-0003 -> beads:bd-a13f, beads:bd-f821
J0123456789abcdefabcd-0004 -> beads:bd-f821
J0123456789abcdefabcd-0005 -> beads:bd-a13f
```

If the user or agent pauses one Bead and switches to another, record that switch only when forgetting it would cause a future reader to make a wrong inference. For example, make clear that switching away from a Bead does not imply it was completed.

Actual task status still belongs in Beads.

## Starting or resuming work

Follow the project's Beads integration and Beads skill when present. Current Beads integrations may inject `bd prime` automatically; otherwise `bd prime` provides Beads workflow/project context.

For programmatic use, prefer Beads JSON output when available:

```text
bd ready --json
bd show <id> --json
```

When an agent picks up work directly, Beads supports atomic claiming:

```text
bd update <id> --claim --json
```

These commands are Beads workflow, not session-journey workflow. Do not add Beads as a dependency of `scripts/journey.py`.

## `bd remember` is not session memory

Beads also supports persistent project memories through `bd remember`, which `bd prime` can surface to future Beads-aware agents.

Treat that as **hot, distilled project memory**, not as a replacement for the append-only session journey.

Use this distinction:

- the journey file: what happened to understanding during a particular session; historical, episodic, append-only, retrieved when relevant.
- `bd remember`: a very small durable project fact worth placing into future Beads context.
- docs / ADRs / tests / lint / CI: canonical durable knowledge or enforceable project rules when the project has such a home.

Do not call `bd remember` for every journey entry. Do not copy a whole journey into Beads memory.

Example progression:

```text
journey event:
We first tried direct release pushes, discovered protected main rejects them, and pivoted to a PR-based flow.

possible distilled Beads memory:
Release automation cannot depend on direct pushes to protected main.

possible ADR:
Why release version synchronization uses a PR-based design, including alternatives and consequences.
```

Keep the original journey event as provenance even if a durable fact is later promoted elsewhere.

## Beads notes are not a second journey

Do not duplicate the session journey into Beads comments or notes.

Use a Beads note/comment only when the information is specifically useful for executing or handing off that Bead. Keep session history, abandoned paths, and epistemic pivots in the journey.

Bad duplication:

```text
journey file: full pivot history
Beads notes: same full pivot history copied again
```

Better separation:

```text
Beads: task description, acceptance criteria, status, dependencies, concise task-specific handoff
Journey: why our understanding changed, failed approaches, corrections, pivots
```

## Interoperability rules

When Beads is present, preserve these invariants:

1. Beads is authoritative for actionable work state.
2. Session journey is authoritative for append-only episodic session memory.
3. Journey events may reference Beads IDs, but Beads remains optional.
4. When a discovery becomes actionable work, create or update a Bead rather than turning the journey into a TODO list.
5. Do not mirror Beads state into the journey.
6. Do not mirror the whole journey into Beads notes or memories.
7. Use `bd remember` only for tiny durable project facts that deserve hot future context; never as an automatic promotion target.
8. Do not make `scripts/journey.py` invoke `bd` or require Beads to be installed.
