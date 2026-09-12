# Session Journey

Minimal append-only episodic memory for coding-agent sessions.

Session Journey records only discoveries, decisions, pivots, corrections,
failed approaches, blockers, and unresolved questions that would be expensive
to rediscover after context compaction, handoff, or restart. It does not store
transcripts, routine progress, TODOs, or task state.

## Install

Install globally for Codex:

```bash
npx skills@latest add esa-zz/session-journey --skill=session-journey --agent=codex --global --yes
```

Or choose scope and supported agents interactively:

```bash
npx skills@latest add esa-zz/session-journey
```

Restart the agent if the skill does not appear immediately. Invoke it explicitly
as `$session-journey`, or let the agent activate it when a session needs durable
episodic memory.

## Requirements

- Python 3.10 or newer
- No Python packages or shell-specific runtime dependencies

Journey files are written inside the active project under `.memory/sessions/`.
The helper owns their IDs, timestamps, append operations, and structural
validation.

## Update

```bash
npx skills@latest update session-journey --global
```

## Development

Validate the helper:

```bash
python -m unittest discover -s tests
```

Validate skill metadata with Codex's bundled `skill-creator` validator:

```bash
python /path/to/skill-creator/scripts/quick_validate.py .
```

## License

MIT
