# Agent Instructions

Standalone instruction files designed to be **explicitly mentioned** (`@file`) in AI coding assistant conversations.

## When to Use Instructions (vs Skills)

Use an instruction file here when:

- The task is **situational** — only relevant in specific contexts, not worth auto-loading on every conversation.
- The instruction is **long or detailed** enough that embedding it in a skill description would waste tokens on irrelevant turns.
- You want **precise, manual control** over when the assistant reads it.

If a workflow is generic enough to trigger automatically based on context, consider registering it as a [skills](../skills/) instead.

## Usage

Mention any file in this directory to attach it to your conversation:

```
@dev-agents/instructions/<filename>.md
```
