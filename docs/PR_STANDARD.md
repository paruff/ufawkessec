# PR Naming Standard — ufawkessec

> Enforced by CI via Conventional Commits check.
> Every PR title must pass before merge.

---

## Format

```
type(scope): lowercase description
```

### Rules

1. **Type** — one of: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`
2. **Scope** — optional, lowercase, in parentheses: `(ci)`, `(scanner)`, `(policy)`, `(deps)`
3. **Colon-space** — exactly `: ` (colon followed by one space)
4. **First word after colon** — MUST be lowercase `[a-z]`
5. **Description** — free text, keep under 72 characters

### Examples

| ✅ Valid | ❌ Invalid | Why |
|---|---|---|
| `feat(ci): add main ci guard` | `feat(ci): Add main ci guard` | Description starts uppercase |
| `fix(scanner): correct trivy threshold` | `fix(scanner):correct threshold` | Missing space after colon |
| `chore(deps): bump trivy version` | `chore: Bump trivy version` | Description starts uppercase |
| `docs: update PR standard` | `docs:Update PR standard` | Missing space |
| `feat(policy): add semgrep rules` | `feat(policy): Add semgrep rules` | "Add" uppercase |

### CI Gate Log

When a PR title fails, CI rejects it with:

```
PR title does not follow Conventional Commits.
Expected: type(scope): description
```

### Branch Naming

- `feat/<slug>` — new features
- `fix/<slug>` — bug fixes
- `chore/<slug>` — maintenance, deps, CI
- `docs/<slug>` — documentation only

### CI Requirements

Before merge, ALL of the following must pass:
- `ci.yml` — pre-commit hooks
- `ci-pipeline.yml` — full pipeline (lint, security, build, tests)
- `main-ci-guard.yml` — verifies main CI is healthy
