---
description: This file describes the git workflow expectations for Copilot agents contributing to this repository.
applyTo: "**"
---

## Git Workflow Expectations for Copilot Agents

When an agent performs git operations for this repository, follow these rules:

### Branching
- Never develop directly on `main` when a task requires code changes and a branch can be created.
- Create or switch to a task-specific branch before editing when requested to implement work that should be proposed via PR.
- Use concise, descriptive branch names with a stable prefix, for example: `feature/<short-topic>`, `fix/<short-topic>`, or `chore/<short-topic>`.

### Commits
- Do not create commits unless the user explicitly asks for a commit.
- Keep commits scoped to the task; do not include unrelated modified files.
- Write clear commit messages in imperative mood that summarize user-visible intent.
- Prefer one focused commit per logical change set unless the user asks for a different commit strategy.
