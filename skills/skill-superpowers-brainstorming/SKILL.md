---
name: skill-superpowers-brainstorming
description: Brainstorm and shape high-leverage Codex skill ideas from rough concepts. Use when the user asks to brainstorm, ideate, explore, refine, name, scope, compare, or turn a vague "skill superpower" idea into concrete skill concepts, trigger descriptions, workflows, examples, guardrails, and a build-ready skill brief.
---

# Skill Superpowers Brainstorming

## Overview

Use this skill to help the user discover what a new Codex skill should make possible, especially when the initial idea is fuzzy, ambitious, or expressed as a "superpower." Move between expansive ideation and practical skill design until the user has a clear direction or a build-ready brief.

## Conversation Posture

Start collaborative and curious. Prefer making the user's implicit taste visible over forcing a rigid framework too early.

Ask at most two clarifying questions before generating options unless the user explicitly wants an interview. If the user's intent is already clear enough, make reasonable assumptions and start brainstorming.

Treat brainstorms as a design surface, not a list dump. Include surprising directions, practical directions, and one or two deliberately weird-but-useful directions when appropriate.

## Core Workflow

### 1. Frame the Seed

Restate the rough idea as a capability: "This skill helps Codex..." Then identify:

- User problem: what recurring frustration or opportunity it addresses
- Agent advantage: what procedural knowledge, workflow, resource, or constraint would make Codex better
- Reuse signal: what would happen often enough to justify a skill
- Output shape: what the user should receive after invoking the skill

### 2. Diverge

Generate 5-9 candidate skill directions. Give each a short name, a one-sentence superpower, and a concrete example prompt that would trigger it.

Vary the candidates across these lenses:

- Workflow accelerator: makes a known process faster or more reliable
- Taste amplifier: captures preferences, voice, design rules, or decision style
- Quality gate: checks work against standards, risks, tests, or edge cases
- Research guide: knows where to look and what to verify
- Artifact builder: creates or edits a recurring file type or deliverable
- Coach or collaborator: improves thinking, reflection, practice, or planning

### 3. Pressure-Test

For the strongest candidates, assess:

- Trigger clarity: would Codex know when to use it from metadata alone?
- Skill fit: does it contain durable procedural knowledge beyond a normal prompt?
- Resource needs: would scripts, references, or assets make it materially stronger?
- Scope risk: is it too broad, too narrow, or dependent on missing context?
- Validation path: how could the user tell whether it works?

### 4. Converge

Recommend 1-3 best directions. Explain the tradeoff in plain language and invite the user to choose, combine, or mutate them.

If the user wants to build the skill, produce a brief with:

- Skill name in lowercase hyphen-case
- Frontmatter description with specific trigger contexts
- Core workflow sections for `SKILL.md`
- Example user prompts
- Suggested resources, if any
- Validation examples

## Output Formats

Use the smallest format that helps the user move forward.

For early ideation:

```markdown
Here are 7 possible skill superpowers:

1. `skill-name`
   Superpower: ...
   Trigger prompt: ...
   Why it works: ...
```

For selection:

```markdown
My top three:

1. `best-name` - Best if you want ...
2. `second-name` - Best if you want ...
3. `third-name` - Best if you want ...
```

For a build-ready brief:

```markdown
Skill brief

Name: `skill-name`
Description: ...
Core workflow:
- ...
Resources:
- None, or scripts/references/assets with reasons
Validation prompts:
- ...
```

## Guardrails

Avoid treating every idea as skill-worthy. Say when a prompt template, project convention, automation, or normal conversation would be enough.

Avoid producing huge taxonomies unless the user asks for breadth. Prefer a memorable set of options with sharp distinctions.

Avoid overfitting to the current conversation. A real skill should work for future users and future tasks from metadata plus concise procedural guidance.
