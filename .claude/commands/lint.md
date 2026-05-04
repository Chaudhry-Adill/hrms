---
description: Run ruff and prettier across the codebase
---

Run the project's linting and formatting tools.

For Python files:
```bash
ruff check --fix .
ruff format .
```

For frontend JS/Vue files:
```bash
cd frontend && npx prettier --write .
```

For roster JS/Vue files:
```bash
cd roster && npx prettier --write .
```

If any fixes were made, report which files were changed.
