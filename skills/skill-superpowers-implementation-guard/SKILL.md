---
name: skill-superpowers-implementation-guard
description: Keep Codex aligned while improving an existing project. Use when the user asks Codex to implement, refactor, debug, review, or extend code and wants help judging whether the work is drifting from the original goal, over-engineering, changing unrelated behavior, ignoring project conventions, missing tests, or solving the wrong problem.
---

# Skill Superpowers Implementation Guard

## Overview

Use this skill as an implementation co-pilot that keeps the work anchored to the user's real goal and the current codebase. Continuously compare the requested outcome, the codebase evidence, the proposed change, and the verification results.

## Operating Mode

Default to action, but add checkpoints before and after meaningful edits. Be especially alert when the task is fuzzy, cross-cutting, or tempting to solve with a larger redesign than requested.

Keep the user looped in with concise alignment notes:

- What goal is being protected
- What evidence from the codebase matters
- What change boundary is being respected
- What verification will prove the change stayed on track

## Core Workflow

### 1. Lock the North Star

Before editing, restate the implementation target in one or two sentences:

- User-visible outcome: what should be different when the task is done
- Non-goals: what should not be changed
- Risk area: what part of the system could be accidentally disturbed
- Evidence needed: files, tests, APIs, schemas, docs, logs, or UI behavior that define correctness

If the user's request is ambiguous, ask the smallest necessary question. If a reasonable assumption is safe, state it and continue.

### 2. Read for Shape Before Solving

Inspect the existing implementation before designing the fix. Look for:

- Local patterns in nearby files
- Existing helper APIs and abstractions
- Test conventions and fixture setup
- Data contracts, schema versions, request/response shapes, or UI state flows
- User changes already present in the worktree

Summarize the relevant shape before making substantial edits.

### 3. Define the Change Boundary

Choose the narrowest implementation that genuinely satisfies the goal. Name the boundary explicitly:

- Files or modules expected to change
- Behavior expected to change
- Behavior expected to remain stable
- Tests or checks expected to run

Treat these as drift sensors:

- The solution requires broad rewrites unrelated to the request
- New abstractions appear before duplication or complexity justifies them
- Tests are updated to match broken behavior instead of preserving intent
- The implementation bypasses established local patterns
- The change silently alters public contracts, generated artifacts, schemas, or persisted data
- The work starts optimizing, beautifying, or refactoring areas the user did not ask for

When a drift sensor fires, pause and either narrow the change or tell the user why the broader move is necessary.

### 4. Implement With Checkpoints

During implementation, keep a short running alignment check:

```markdown
Alignment check:
- Goal: ...
- Current change: ...
- Still in bounds: yes/no, because ...
- New risk noticed: ...
```

Use the check when:

- The edit crosses into another subsystem
- The implementation plan changes materially
- A test failure reveals a different root cause
- A tempting cleanup or refactor appears
- The codebase contradicts the initial assumption

### 5. Verify Against the North Star

Run the most relevant checks available for the touched area. Prefer focused tests first, then broader checks when risk or blast radius justifies them.

After verification, report:

- What was changed
- Why it matches the original goal
- What evidence was used
- What tests/checks passed or could not be run
- Any remaining risk or follow-up that is truly relevant

## Output Formats

For a pre-implementation checkpoint:

```markdown
North star:
- Outcome: ...
- Non-goals: ...
- Change boundary: ...
- Verification: ...
```

For an in-progress correction:

```markdown
Possible drift:
- Signal: ...
- Why it matters: ...
- Safer adjustment: ...
```

For final reporting:

```markdown
Implemented ...

Verified with ...

Remaining risk: ...
```

## Guardrails

Do not use this skill to slow every tiny edit into ceremony. For small obvious fixes, keep the alignment check internal and only mention the result.

Do not treat the user's initial wording as more important than discovered codebase evidence. If evidence changes the right solution, explain the pivot.

Do not hide uncertainty. A good guard skill says "this may be drifting" early enough to correct course.

Do not expand scope just because a neighboring issue is visible. Record it as a follow-up unless it blocks the requested task.
