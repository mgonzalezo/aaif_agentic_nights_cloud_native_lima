---
name: release-notes
description: How to draft release notes for a farolito tag. Use when preparing a release.
---

# Draft release notes

1. Collect the `[Unreleased]` entries from CHANGELOG.md.
2. Move them under a new heading `## [x.y.z] - YYYY-MM-DD`.
3. Write a two-sentence summary at the top for people who only read the first lines.
4. List breaking changes first, with a migration hint for each.
5. Thank every first-time contributor by GitHub handle.
6. Bump `__version__` in `farolito/__init__.py` in the same pull request.
7. Tag only after CI is green on `main`.
