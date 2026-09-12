# Session Journey

Minimal append-only episodic memory for coding-agent sessions.

Session Journey records the parts of a coding session that would be expensive to rediscover later. It keeps discoveries, decisions, failed approaches, pivots, corrections, blockers, important unexecuted plans, and unresolved questions.

It does not try to remember everything the agent did. It preserves changes in understanding.

## What Session Journey is

A coding session is not the same thing as a task. One session can touch several tasks, abandon an approach, discover a new constraint, switch direction, and later correct an earlier assumption.

Session Journey keeps that history in one append-only Markdown file per session:

```text
.memory/sessions/YYYY/MM/DD/HHMMSSZ_<uuid>.md
```

The agent decides whether an event is worth remembering. A small Python helper handles deterministic mechanics such as session paths, IDs, fingerprints, locking, validation, and append-only writes.

Existing events are never edited. If an earlier event becomes wrong, the agent appends a correction. If a plan is abandoned, it appends a pivot. The older event remains in the file so a later agent can see how the understanding changed.

## Why it exists

Coding agents lose context through compaction, handoff, restart, and session boundaries. Some information is cheap to recover from the repository. Other information is not.

For example, an agent may spend time proving that a plausible fix cannot work because of a repository constraint. Without a record of that result, a later session may repeat the same investigation.

Session Journey stores that kind of evidence without storing the full conversation or execution trace.

## What belongs in a journey

Typical events include:

- `discovery`: a fact that changes how the problem should be understood
- `decision`: a choice whose reason may matter later
- `plan`: an important intended approach, including plans that were never executed
- `failure`: an approach that failed and the reason it failed
- `pivot`: a change in direction after new evidence
- `correction`: a later event that fixes an earlier belief
- `blocker`: a constraint that prevents progress
- `question`: an unresolved question that is expensive to reconstruct

Record an event if forgetting it could make a later agent repeat an expensive dead end, confuse intent with execution, miss a changed constraint, or lose the reason for a decision.

Routine commands, test output, files that were merely inspected, and ordinary implementation progress usually do not belong in the journey.

## How it works

The skill creates a journey lazily. A trivial session can finish without creating one.

When the agent finds something worth preserving, it starts the session journey if needed and appends a small event. Event IDs belong to that session and increase in order.

A simplified journey can look like this:

```markdown
## J...-0003 plan

Status: NOT EXECUTED.

Try the direct release push approach.

## J...-0005 failure

Refs: J...-0003

Protected main rejects the direct push.

## J...-0006 pivot

Refs: J...-0003, J...-0005

Use a pull-request-based release flow instead.
```

The history stays intact. The journey records what changed, not just the final answer.

## What Session Journey does not try to be

Session Journey has a narrow job. Keeping that boundary is part of the design.

It is not a transcript or chain-of-thought store. It does not save the conversation, hidden reasoning, tool traces, command history, or routine test output.

It is not a task tracker. Status, priority, dependencies, ownership, acceptance criteria, and completion belong in a task system such as GitHub Issues, Beads, Linear, or ClickUp. Journey events can keep opaque references to those systems without copying their state.

It is not project documentation. Stable architecture, workflows, conventions, and long-lived decisions belong in project docs or ADRs. A journey can preserve the session evidence that led to a durable document, but it does not replace that document.

It is not a search engine or vector database. The current helper does not provide semantic search, embeddings, ranking, automatic retrieval, deduplication, or lifecycle management. Those can be added as derived indexing layers without changing the append-only journey files.

It is not an automatic summarizer. The helper does not decide what matters and does not rewrite a session into a clean final narrative. The agent records specific events when they become worth remembering.

It is not an authentication system. Session fingerprints and event namespaces catch structural mismatches. They do not protect against a malicious writer who can modify repository files.

## Pros and cons

| Property | Benefit | Cost |
| --- | --- | --- |
| Append-only history | Preserves failed ideas, corrections, and pivots instead of rewriting them away | Old beliefs remain in the file and must be interpreted with later corrections |
| Plain Markdown | Easy to inspect, diff, version, grep, and move with the repository | No built-in semantic retrieval or ranking |
| One file per session | Keeps session provenance explicit and easy to browse | Large numbers of sessions need a separate retrieval strategy |
| Agent-selected events | Avoids storing routine noise | Memory quality depends on the agent choosing useful events |
| Small Python helper | No database or Python package dependency | The helper intentionally provides only a small command set |
| Task-system independence | Works without coupling memory to one issue tracker | Task status must be retrieved from the external task system |
| Separate durable docs | Avoids turning session history into project documentation | Important discoveries may need promotion into docs or ADRs later |

## When it fits

Session Journey is a good fit when you want a small repository-local record of session discoveries and dead ends, and you care about preserving how the agent's understanding changed.

It is a poor fit if you need a complete activity log, centralized cross-project memory, automatic semantic recall, live task coordination, or a database that continuously rewrites and ranks memories. Use systems designed for those jobs instead.

## Install

Install globally for Codex:

```bash
npx skills@latest add esa-zz/session-journey --skill=session-journey --agent=codex --global --yes
```

Or choose scope and supported agents interactively:

```bash
npx skills@latest add esa-zz/session-journey
```

Restart the agent if the skill does not appear immediately. Invoke it explicitly as `$session-journey`, or let the agent activate it when a session needs durable episodic memory.

## Requirements

- Python 3.10 or newer
- No Python packages or shell-specific runtime dependencies

Journey files are written inside the active project under `.memory/sessions/`. The helper owns their IDs, timestamps, append operations, locking, and structural validation.

## Update

```bash
npx skills@latest update session-journey --global
```

## Development

Run the test suite:

```bash
python -m unittest discover -s tests
```

Validate skill metadata with Codex's bundled `skill-creator` validator:

```bash
python /path/to/skill-creator/scripts/quick_validate.py .
```

## License

MIT
