---
name: open-upstream-pr
description: How to open a pull request to farolito upstream (branch naming, DCO sign-off, PR template). Use when a fix is ready to submit.
---

# Open an upstream pull request

1. Branch name: `fix/<issue-number>-<short-slug>`, for example `fix/7-missing-config`.
2. Every commit needs a DCO sign-off line: `Signed-off-by: Name <email>`.
3. PR title: `<area>: <what changed>`, for example `cli: friendly error when config is missing`.
4. PR body must use this template:

```
Fixes #<issue-number>

## What changed
<one or two sentences>

## How I tested it
`python -m pytest -q`
```

5. Never push to `main` and never delete branches.
