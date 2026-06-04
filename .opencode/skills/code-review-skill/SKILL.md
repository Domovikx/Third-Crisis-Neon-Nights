---
name: code-review-skill
description: Review parser/translator code and translation workflow. Checks .py scripts, C# runtime, configs, and .ndjson translation files. Provides structured feedback with severity, location, explanation, and recommendation.
---

## What I do

I review code across the codebase:

- **Parser code** — `.py` scripts, logic, edge cases, error handling
- **Runtime code** — `.cs`/`.dll` translation runtime
- **Translation files** — `.ndjson` dialogue, UI, character files
- **Configs** — `.json`, `.ps1`, build scripts
- **Workflow** — completeness of translation pipeline (extract → translate → build)

## How I give feedback

Each review item contains:

```
<severity> <location> <explanation> <recommendation>
```

**Severities:**

| Level    | Meaning                              |
| -------- | ------------------------------------ |
| `error`  | Bug, crash, or data loss risk        |
| `warn`   | Logic concern, fragile code          |
| `info`   | Style, docs, minor improvement       |
| `praise` | Well-written code worth highlighting |

**Location:** `file:line` or `filename`

## When NOT to use me

- General code review unrelated to translation
- UI/UX feedback
- Game design or balance review
- Other runtime code outside translation scope

## Triggers

Use when working on translation pipeline or when the user asks to "check" or "review" parser/runtime/translator code.
