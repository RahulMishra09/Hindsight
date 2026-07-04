# Hindsight — Weekly Progress Log

Each entry follows the same template. Fill every section; write "none" rather than omitting.

---

## Template (copy for each new week)

```markdown
## Week N — YYYY-MM-DD to YYYY-MM-DD

### Shipped
- ...

### Cut (descoped this week, not permanently)
- ...

### Carried Over (from previous week)
- ...

### Metrics
- Lines of application code added:
- Test count (unit / integration / e2e):
- Coverage %:
- Open issues closed:

### Risks
- ...
```

---

## Week 0 — 2026-07-04 to 2026-07-04

### Shipped

- Repository skeleton: all package directories with `__init__.py`; non-Python dirs with `.gitkeep`.
- `docs/SAD.md` — full System Architecture Document (20 sections).
- `CLAUDE.md` — root-level AI assistant context with stack, rules, and descoped list.
- `docs/PROGRESS.md` — this file, with weekly template.
- `docs/adr/0001-postgres-for-everything.md` — ADR for single-store PostgreSQL + pgvector.
- `docs/adr/0002-redis-streams-over-kafka.md` — ADR for Redis Streams event bus.
- `pyproject.toml` — uv-managed project with Python 3.12 pin; ruff (line-length 100, isort) and mypy strict configured.
- `uv.lock` — committed lockfile.
- `.pre-commit-config.yaml` — ruff lint+format, mypy, gitleaks, EOF/trailing-whitespace hooks.
- `.gitignore` — Python, Node, `.env`, `data/raw/`, `models/`, `*.onnx`, wandb, `.DS_Store`.
- `.env.example` — all environment variables enumerated with comments.
- `CONTRIBUTING.md` — setup, commit convention, PR expectations.
- `README.md` — project name, pitch, "under construction" notice, badge placeholders.
- `frontend/README.md` — placeholder noting Week 4 scaffold.
- `.editorconfig` — consistent editor settings.
- `.github/workflows/ci.yml` — pre-commit + pytest on every push/PR.
- `.github/workflows/publish.yml` — documented stub for HF Hub releases (Week 3/5).
- `tests/unit/test_sanity.py` — trivial passing test proving CI is not vacuously green.
- All pre-commit hooks pass on the committed codebase.
- CI green on `main`.

### Cut

- none

### Carried Over

- none (Week 0 is the first entry)

### Metrics

- Lines of application code added: 0 (Week 0 is infrastructure only)
- Test count (unit / integration / e2e): 1 / 0 / 0
- Coverage %: N/A (no application code)
- Open issues closed: 0

### Risks

- `gitleaks` hook requires the `gitleaks` binary to be installed on developer machines; document in CONTRIBUTING.md. Low risk: CI installs it automatically.
- `mypy --strict` on an empty codebase passes trivially; enforcing it becomes meaningful in Week 1 when application code arrives.
