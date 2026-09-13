# Session Journey

![Session Journey: an agent navigating false starts, pivots, and discoveries](img/README.png)

Minimal, harness-agnostic, append-only episodic memory for coding-agent sessions.

Any agent that can load a skill and make a tool call to run a Python command can use it. No SDK, daemon, database, or model-specific integration required.

## Why this exists

I built Session Journey for one failure mode that kept bothering me: an agent can spend half a session proving an approach is wrong, then context compaction or a restart leaves the next agent with only the clean final state. The dead end looks unexplored again. A journey keeps the parts of the session that are expensive to rediscover in one append-only Markdown file: discoveries, decisions, failed approaches, pivots, corrections, blockers, unresolved questions, and plans that matter. It deliberately leaves out transcripts, routine progress, TODOs, and task state, because those already have better homes and I do not want another place where task status can drift. The same goes for project documentation. Stable architecture belongs in docs or ADRs, while the journey keeps the session history that explains how you got there. I compared this boundary with OmniMem while working through the design and came away wanting almost the opposite tradeoff: keep the source record boring and inspectable, then add semantic search, ranking, or other retrieval machinery later as a separate layer if it becomes necessary.

A session is also not a task. One session can touch several tasks, abandon an approach, discover a new constraint, switch direction, and later correct an earlier assumption. That messy sequence is the useful part.

## How it works

Each session gets one file:

```text
.memory/sessions/YYYY/MM/DD/HHMMSSZ_<uuid>.md
```

The agent decides when something is worth remembering. A small Python helper handles the mechanical parts: paths, IDs, fingerprints, locking, validation, and append-only writes.

Existing events are never rewritten. If an earlier event turns out to be wrong, append a correction. If a plan is abandoned, append a pivot. If a plan was never executed, say so instead of quietly turning it into history.

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

The point is not to reconstruct the whole session. It is to keep enough evidence that a later agent does not repeat the expensive parts.

## What is worth writing down

Record an event when forgetting it could make a later agent repeat a dead end, confuse intent with execution, miss a changed constraint, or lose the reason for a decision.

Typical kinds are `discovery`, `decision`, `plan`, `failure`, `pivot`, `correction`, `blocker`, and `question`. The labels are less important than the rule above.

Routine commands, test output, files that were merely inspected, and ordinary implementation progress are usually noise here.

## Tradeoffs

I went with plain Markdown over SQLite because I wanted `git diff`, `grep`, and a normal editor to work without an adapter. That also means retrieval at scale is a problem for later, not something this project pretends to solve today.

Append-only history is intentional. It keeps failed ideas and corrections visible, but it also means an old belief stays in the file after it becomes wrong. I prefer that to silently rewriting history and losing the reason for the correction.

The other sharp edge is selection. The agent decides what deserves memory. That keeps the files small, but a bad judgment call can still save noise or miss something important. I would rather have that failure mode than automatically record every tool call and call it memory.

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

## Update

```bash
npx skills@latest update session-journey --global
```

## Requirements

- Python 3.10 or newer
- No Python packages or shell-specific runtime dependencies

Journey files are written inside the active project under `.memory/sessions/`.

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
