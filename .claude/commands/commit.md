---
description: Create a conventional commit
argument-hint: <type> <message>
allowed-tools: Bash(git add:*), Bash(git commit:*)
---

Create a conventional commit. The first word of "$ARGUMENTS" is the type; the rest is the message.

Allowed types: build, chore, ci, docs, feat, fix, perf, refactor, revert, style, test, patch

If there are no staged changes, stage all modified files with `git add -u` then commit with:
```bash
git commit -m "<type>: <message>"
```

Current staged changes:
!`git diff --cached --stat`
