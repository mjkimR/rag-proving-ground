# AGENTS.md Health Check

Instruction for verifying that the root `AGENTS.md` is accurate, concise, and well-structured.

## Usage

Mention this file in a conversation to trigger the check:

```
@dev-agents/instructions/agents-md-healthcheck.md Run AGENTS.md health check
```

---

## Checks

Perform all 6 checks **in order**. Verdict each as `✅ OK` or `⚠️ Action needed`. Include concrete fix proposals for any `⚠️`.

---

### 1. Workspace Map Sync

**Goal**: Verify the `## Workspace Map` section matches the actual directory tree.

**Steps**:

1. Scan 1–2 depth directories under project root (`apps/`, `packages/`, `infra/`, `scripts/`, `experiments/`, `datasets/`).
2. Compare each directory against the Workspace Map entries.
3. Report two types of drift:
   - **Unregistered**: directory exists but is missing from Workspace Map
   - **Ghost entry**: listed in Workspace Map but does not exist on disk

**Fix criteria**: Propose adding unregistered directories only if they contain meaningful code or config. Ignore cache/temp directories (`.cache`, `__pycache__`, `logs`, etc.).

---

### 2. File Size & Compression

**Goal**: Detect bloat and identify token-efficiency improvements.

**Steps**:

1. Measure line count and byte size of `AGENTS.md`.
2. Apply thresholds:

| Metric | Good | Caution | Warning |
|---|---|---|---|
| Lines | ≤100 | 101–150 | >150 |
| Bytes | ≤7KB | 7–10KB | >10KB |

3. If `Caution` or above, analyze:
   - Prose that can be compressed into bullet points
   - Redundant phrasing or repeated context
   - Unnecessary examples or elaboration

**Fix criteria**: Propose specific compression edits that reduce tokens without altering the meaning of any rule, path, or constraint.

---

### 3. Split Readiness

**Goal**: Assess whether the single root `AGENTS.md` should be split into sub-project files.

**Steps**:

1. Analyze subsections under `## Architecture & Code Style`.
2. For each workspace, count lines of **workspace-specific rules** (rules that apply only to that workspace):
   - `### Python Workspace` — workspace-specific portion
   - `### Backend` — specific rules
   - `### Frontend` — specific rules
3. Apply thresholds:

| Condition | Verdict |
|---|---|
| All workspace-specific sections **<15 lines** | Split not needed |
| Any single workspace-specific section **≥15 lines** | Split recommended |
| Two or more workspace-specific sections **≥15 lines** each | Split strongly recommended |

4. If split is recommended, also report:
   - **Cross-cutting concerns** that must remain in root `AGENTS.md`
   - Rules to move into each sub-project `AGENTS.md` (e.g. `apps/backend/AGENTS.md`)
   - Expected file paths for new AGENTS.md files

> [!IMPORTANT]
> If split is recommended, **this instruction file itself** (`dev-agents/instructions/agents-md-healthcheck.md`) must also be rewritten to account for multiple AGENTS.md files (adjusted scan targets, per-file size thresholds, cross-file consistency checks, etc.). Include this as a required follow-up action in the report.

---

### 4. Skill Extraction Candidates

**Goal**: Identify sections that have grown enough to warrant extraction into a standalone skill.

**Steps**:

1. Evaluate each AGENTS.md section against these criteria:

| Criterion | Description |
|---|---|
| **Volume** | Section is ≥20 lines on its own? |
| **Independence** | Readable as a standalone document without other sections? |
| **Trigger frequency** | Only needed for specific tasks, not general development? |
| **Extensibility** | Could grow with examples, templates, or scripts? |

2. Flag sections meeting **≥3 of 4** criteria as extraction candidates.
3. For each candidate, propose:
   - Suggested skill name and description
   - Expected size reduction in AGENTS.md after extraction
   - Proposed skill structure (`SKILL.md`, optionally `scripts/`, `examples/`)

---

### 5. Sub-project AGENTS.md Scan

**Goal**: Detect AGENTS.md files in subdirectories and check for duplication or conflicts with root.

**Steps**:

1. Search for all `AGENTS.md` files project-wide (`find . -name "AGENTS.md"`).
2. For any AGENTS.md found outside root:
   - Report file location and size.
   - Check for **duplicate rules** (same topic covered in both root and sub-project).
   - Check for **conflicting rules** (same topic, different instructions).
3. Propose consolidation or adjustment if duplication/conflicts exist.

---

### 6. Clarity & Positioning

**Goal**: Avoid instruction decay due to vague language and positional bias ("Lost in the Middle").

**Steps**:

1. **Positioning Check (Lost in the Middle)**:
   - Identify critical rules (e.g., `Critical Constraints`, security rules, DB boundary constraints).
   - Verify if they are located near the top of `AGENTS.md` (e.g., in the upper 20% of the file, or explicitly grouped under a high-priority section).
   - Flag critical rules that are buried in the middle of long prose sections.
2. **Clarity Check (Vague Conditionals)**:
   - Scan the text for weak or ambiguous words that introduce logical gaps (e.g., `should`, `if needed`, `sometimes`, `as much as possible`, `roughly`, `often`, `try to`).
   - Scan for naked pronouns like `this`, `that`, `these` where the referred symbol or context is not explicitly clear.

**Fix criteria**: Propose moving critical constraints to the top/priority sections. Propose rewriting vague guidelines into deterministic instructions (using `MUST`, `NEVER`, `ALWAYS`).

---

## Report Format

Output results as an artifact in this format:

```markdown
# AGENTS.md Health Check Report

**Date**: YYYY-MM-DD
**AGENTS.md size**: XX lines / X.XKB

## Summary

| # | Check | Verdict |
|---|---|---|
| 1 | Workspace Map Sync | ✅ / ⚠️ |
| 2 | File Size & Compression | ✅ / ⚠️ |
| 3 | Split Readiness | ✅ / ⚠️ |
| 4 | Skill Extraction Candidates | ✅ / ⚠️ |
| 5 | Sub-project AGENTS.md Scan | ✅ / ⚠️ |
| 6 | Clarity & Positioning | ✅ / ⚠️ |

## Detailed Results

(Per-check analysis and fix proposals)

## Recommended Actions

(Prioritized list of follow-up tasks)
```

---

## Post-Check Behavior

Select the action based on the execution mode requested by the caller:

### Mode A: Report-Only (Default / Local Agent)
*Use this mode if the caller did not explicitly request auto-fix or PR creation.*
- Output the report detailing the check results and concrete fix proposals.
- **Do not modify any codebase files (including `AGENTS.md`) directly.**

### Mode B: Auto-Fix / PR Mode (Cloud Agent)
*Use this mode only if the caller explicitly requested automatic resolution or PR creation.*
- Generate the check report.
- Apply the proposed fixes directly (e.g., updating `AGENTS.md` Workspace Map, creating sub-project `AGENTS.md` files, or extracting skill files).
- Create a Git branch, apply changes, and submit a pull request (PR) containing these changes. **Use the generated check report as the PR description.**


