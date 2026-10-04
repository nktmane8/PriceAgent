# Contributing
1. Read `docs/ENGINEERING.md` (workflow, Definition of Done) and `docs/DESIGN.md` (architecture).
2. Set up: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt -r requirements-dev.txt`.
3. Run tests (no API key needed): `python -m pytest -q tests`.
4. Branch from `main`, keep PRs small, add tests, update docs and `CHANGELOG.md`.
5. Prompt changes: run `python evals/run_evals.py` before and after and include both pass rates.
6. Never commit secrets, `.env` or database files. Report security issues privately to the maintainer, not in a public issue.
