# Contributing to Hindsight

Thank you for your interest in contributing. This document covers the development setup, commit conventions, and pull request expectations.

---

## Development Setup

**Prerequisites:**
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [pre-commit](https://pre-commit.com/) (installed via uv below)
- [gitleaks](https://github.com/gitleaks/gitleaks) (secret scanner — install separately)
  - macOS: `brew install gitleaks`
  - Linux: see [gitleaks releases](https://github.com/gitleaks/gitleaks/releases)
- Docker (required for integration tests — Week 1+)

**One-time setup:**

```bash
# 1. Clone the repository
git clone https://github.com/<org>/hindsight.git
cd hindsight

# 2. Install dependencies (creates .venv automatically)
uv sync

# 3. Install pre-commit hooks
uv run pre-commit install

# 4. Copy the environment template and fill in values
cp .env.example .env
# Edit .env with your local values (never commit .env)
```

**Verify the setup:**

```bash
# Linting + formatting
uv run ruff check .
uv run ruff format --check .

# Type checking
uv run mypy app ml

# Tests
uv run pytest

# All pre-commit hooks on every file
uv run pre-commit run --all-files
```

All four commands should exit zero on a fresh clone.

---

## Commit Convention

We use [Conventional Commits](https://www.conventionalcommits.org/). Every commit message must match:

```
type(scope): short description

[optional body]

[optional footer]
```

**Types:**

| Type | When to use |
|------|-------------|
| `feat` | New feature or user-visible behaviour |
| `fix` | Bug fix |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `test` | Adding or updating tests |
| `docs` | Documentation only |
| `chore` | Tooling, dependencies, repo housekeeping |
| `ci` | CI/CD configuration changes |

**Scope** should match the package or layer being modified, e.g.:
- `feat(api): add incident list endpoint`
- `fix(workers): handle duplicate content_hash gracefully`
- `test(services): add unit tests for IncidentService`
- `chore(deps): bump ruff to 0.9.10`

**Rules:**
- Subject line ≤ 72 characters, lowercase, no trailing period.
- Use imperative mood: "add endpoint" not "added endpoint".
- Reference issues in the footer: `Closes #42`.

---

## Pull Request Expectations

1. **One logical change per PR.** Split unrelated changes into separate PRs.

2. **Tests are required.** Every PR that touches application code (`app/` or `ml/`) must include or update tests. A PR that adds `app/services/foo.py` must include `tests/unit/test_foo.py`.

3. **Pre-commit hooks must pass.** The CI will reject any PR where `pre-commit run --all-files` fails. Run it locally before pushing.

4. **Mypy strict must pass.** No `type: ignore` comments without an explanatory comment on the same line.

5. **No descoped features.** Do not implement items listed in CLAUDE.md's "Descoped for v1.0" section. If you believe a descoped item should be reconsidered, open an issue to discuss first.

6. **Architecture rules.** Review the rules in CLAUDE.md before submitting. Violations (e.g., business logic in a router, SQLAlchemy imports outside repositories) are blockers.

7. **PR description.** Briefly explain _what_ changed and _why_. Link to the relevant issue.

---

## Running Specific Test Suites

```bash
# Unit tests only (fast, no Docker)
uv run pytest tests/unit/

# Integration tests (requires Docker)
uv run pytest tests/integration/ -m integration

# E2E tests (requires full stack)
uv run pytest tests/e2e/ -m e2e

# All tests with coverage (Week 2+)
uv run pytest --cov=app --cov=ml --cov-report=term-missing
```

---

## Questions?

Open an issue on GitHub or start a discussion. For security vulnerabilities, follow the process in SECURITY.md (coming soon).
