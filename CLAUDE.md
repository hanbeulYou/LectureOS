# CLAUDE.md

This is the Claude Code entry point for the LectureOS repository. Its only job is
to make the repository's durable operating policy load automatically. It defines
no policy of its own; the authoritative rules live in `AGENTS.md`.

## Authoritative operating manual

The single source of truth for how agents work in this repository is `AGENTS.md`.
It is imported below so Claude Code loads it automatically at session start:

@AGENTS.md

`AGENTS.md` is tool-agnostic and is also read directly by Codex and other agents.
Do not restate its rules here or in milestone prompts — inherit them.

## On-demand references (not auto-loaded; read when relevant)

These are pointers, not imports. Read them only when a task requires them so they
do not weigh down every session:

- Detailed implementation workflow — `implementation/050_IMPLEMENTATION_WORKFLOW.md`
- Independent code-review procedure — `.claude/review-code.md`
- Review-resolution procedure — `.claude/review-fix.md`
- Current implementation status — `implementation/060_IMPLEMENTATION_STATUS.md`
- Blueprint (product contracts, domain meaning, released schema, pipelines) — `docs/`, `patches/`

## Precedence

- Blueprint (`docs/`, `patches/`) defines product meaning.
- `AGENTS.md` defines durable agent operating policy.
- `implementation/050_IMPLEMENTATION_WORKFLOW.md` owns the detailed workflow.
- A milestone prompt selects only the current capability and inherits everything above.
